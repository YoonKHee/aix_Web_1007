import re

from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction

from .filters import get_matcher
from .models import Comment, Post, Profile

User = get_user_model()
MIN_PASSWORD = 6
RESERVED = ('admin', 'administrator', 'root', '관리자', '운영자', '운영진')


class SignupForm(forms.Form):
    username = forms.CharField(label='아이디', min_length=4, max_length=20,
                               help_text='영문·숫자·밑줄(_) 4~20자')
    nickname = forms.CharField(label='별명', min_length=2, max_length=12,
                               help_text='한글·영문·숫자·밑줄(_) 2~12자')
    password1 = forms.CharField(label='비밀번호', widget=forms.PasswordInput, max_length=128,
                                help_text=f'{MIN_PASSWORD}자 이상')
    password2 = forms.CharField(label='비밀번호 확인', widget=forms.PasswordInput, max_length=128)

    def clean_username(self):
        v = self.cleaned_data['username'].strip()
        if not re.fullmatch(r'[A-Za-z0-9_]{4,20}', v):
            raise forms.ValidationError('아이디는 영문, 숫자, 밑줄(_)만 쓸 수 있습니다.')
        if User.objects.filter(username__iexact=v).exists():
            raise forms.ValidationError('이미 사용 중인 아이디입니다.')
        if any(r in v.lower() for r in RESERVED) or v.lower().startswith('ai_'):
            raise forms.ValidationError('사용할 수 없는 아이디입니다.')
        if get_matcher().find(v):
            raise forms.ValidationError('아이디에 사용할 수 없는 표현이 들어 있습니다.')
        return v

    def clean_nickname(self):
        v = self.cleaned_data['nickname'].strip()
        if not re.fullmatch(r'[0-9A-Za-z가-힣_]{2,12}', v):
            raise forms.ValidationError('별명은 한글, 영문, 숫자, 밑줄(_)만 쓸 수 있습니다. (공백 불가)')
        if Profile.objects.filter(nickname__iexact=v).exists():
            raise forms.ValidationError('이미 사용 중인 별명입니다.')
        if any(r in v.lower() for r in RESERVED):
            raise forms.ValidationError('사용할 수 없는 별명입니다.')
        if get_matcher().find(v):
            raise forms.ValidationError('별명에 사용할 수 없는 표현이 들어 있습니다.')
        return v

    def clean_password1(self):
        v = self.cleaned_data['password1']
        if len(v) < MIN_PASSWORD:
            raise forms.ValidationError(f'비밀번호는 {MIN_PASSWORD}자 이상이어야 합니다.')
        return v

    def clean(self):
        data = super().clean()
        p1, p2 = data.get('password1'), data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', '비밀번호가 서로 다릅니다.')
        return data

    @transaction.atomic
    def save(self):
        d = self.cleaned_data
        user = User.objects.create_user(username=d['username'], password=d['password1'])
        Profile.objects.create(user=user, nickname=d['nickname'])
        return user


def _check_words(value, what):
    w = get_matcher().find(value)
    if w:
        raise forms.ValidationError(f'{what}에 사용할 수 없는 표현("{w}")이 들어 있습니다. 고쳐서 다시 올려주세요.')


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'content']
        widgets = {'title': forms.TextInput(attrs={'placeholder': '제목을 입력하세요', 'maxlength': 100}),
                   'content': forms.Textarea(attrs={'rows': 14, 'placeholder': '내용을 입력하세요'})}

    def clean_title(self):
        v = self.cleaned_data['title'].strip()
        if len(v) < 2:
            raise forms.ValidationError('제목은 2자 이상 입력해주세요.')
        _check_words(v, '제목')
        return v

    def clean_content(self):
        v = self.cleaned_data['content'].strip()
        if len(v) < 2:
            raise forms.ValidationError('내용을 2자 이상 입력해주세요.')
        if len(v) > 5000:
            raise forms.ValidationError('내용은 5000자까지 쓸 수 있습니다.')
        _check_words(v, '내용')
        return v


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']

    def clean_content(self):
        v = self.cleaned_data['content'].strip()
        if not v:
            raise forms.ValidationError('댓글 내용을 입력해주세요.')
        _check_words(v, '댓글')
        return v
