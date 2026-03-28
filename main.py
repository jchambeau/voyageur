from datetime import datetime

print('this is the current date and time:', datetime.now())

def show_date() -> None:
    print('this is the current date and time:', datetime.now())

show_date()

def greet(name: str) -> None:
    print(f'coucou, {name} !')

greet('jacques')



