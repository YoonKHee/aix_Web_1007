-- 테이블 확인
select * from tab;

-- select:검색 ,insert:입력, update:수정, delete:삭제
-- commit:적용, rollback:되돌리기(commit까지)
-- row 데이터 검색
select * from member;

-- table 안에 있는 컬럼 유형
desc member;

select * from employees;

desc employees;

--select employee_id, emp_name, department_id from employees;
-- 기존 값에 계산을 해서 볼수있음. 대부분 db안에서 해결 가능함. 실시간데이터는 하기 어려움
select emp_name,salary ,salary*1342+(salary*1342*0.02) as k_salary from employees; -- 계산값을 변수로 바꿔서 사용

select sysdate, sysdate+100 from member;



-- number, char, varchar2, date 타입
-- numver : +,-,*,/ 가능
-- date : +,- 가능
-- varchar2 : 사칙연산 안됨
select '가'||'나' from dual; -- 문자열타입: || 두 문자를 합침.
select emp_name, email, emp_name||email from employees;


----------------------------------------------------------------
-- 연산자
-- salary, 원화로 월급 원화로 연봉을 출력

select salary, salary*30 as month_salary, salary*30*12 year_salary from employees;


----------------------------------------------------------------
-- 판매부서 에서만 commission : (salary+salary*commitssion_pct)이 있음
desc employees;
-- nvl(컬럼,0) : 없을때는 0으로 변경
--"  "(쌍따옴표) : 특수문자, 한글 등을 사용할수 있음
select salary,commission_pct,salary+salary*nvl(commission_pct,0) "실제월급" from employees;


-- Quiz : 부서 테이블을 모든 컬럼을 출력하시오, 번호, 부서이름 출력
select * from departments;
select department_id,department_name from departments;
select department_id || '부서는'||department_name from departments;

-- distinct 중복을 제거.
select distinct department_id from employees;


-- job_id 중복제거후 출력
select * from employees;
select distinct job_id from employees;

select * from jobs;

select department_id from employees;
select department_id, department_name from departments;

select employees.department_id, department_name from employees, departments;
where employees.department_id = departments.department_id


-- where 조건절 : 비교 <,>,<=,>=,=
-- 2개 이상 and, or
select salary from employees;
select emp_name,salary from employees
where salary>5000;
select salary from employees
where salary = 6000;

select employee_id,salary from employees
where salary >= 6000 and department_id=50;


-- 급여가 4000이하의 사원번호, 사원이름, 급여를 출력
select * from employees;
select employee_id,emp_name,salary from employees
where salary <= 4000;

select hire_date from employees;
-- 날짜비교
select hire_date from employees
where hire_date > '07/01/01';
select hire_date from employees
where hire_date > '07-01-01';
select hire_date from employees
where hire_date > '2007/01/01' and hire_date <='07/12/31';
--select hire_date from employees
--where hire_date > '07년01월01일; 불가


-- 부서번호가 50 이면서 월급 8000인사람
-- 부서번호가 10 이거나 30이거나 100인 사원을 출력
select * from employees
where department_id = 50 and salary >= 8000;
select * from employees
where department_id =10 or department_id=30 or department_id =100;