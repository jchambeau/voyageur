from datetime import datetime
from enum import nonmember

print('this is the current date and time:', datetime.now())

def show_date() -> None:
    print('this is the current date and time:', datetime.now())

show_date()

def greet(name: str) -> None:
    print(f'coucou, {name} !')

greet('jacques')

class Car:
    def __init__(self, brand: str, horsep: int) -> None:
        self.brand = volvo
        self.horsep = horsep

volvo: Car = Car('red', 200)

