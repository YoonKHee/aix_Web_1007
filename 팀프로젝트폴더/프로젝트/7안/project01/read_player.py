import pandas as pd
import os

# read_player.py가 있는 폴더 위치
base_dir = os.path.dirname(os.path.abspath(__file__))

# 선수 기록 파일 위치
file_path = os.path.join(
    base_dir,
    'data',
    'player',
    '2026_강원.xls'
)

print('현재 파이썬 파일 위치 :', base_dir)
print('파일 위치 :', file_path)
print('파일 존재 여부 :', os.path.exists(file_path))


# HTML 형식으로 되어 있는 xls 파일 읽기
tables = pd.read_html(file_path)

print('찾은 테이블 개수 :', len(tables))

# 첫 번째 테이블 가져오기
df = tables[0]

print('데이터 크기 :', df.shape)

print('\n===== 컬럼명 =====')
print(df.columns.tolist())

print('\n===== 처음 5줄 =====')
print(df.head())

print('\n===== 마지막 5줄 확인 =====')
print(df.tail())

print('\n===== 40번째 행 전체 =====')
print(df.iloc[39].to_string())