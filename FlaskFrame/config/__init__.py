# _*_ coding: utf-8 _*_

"""Script content introduction
__author__ = 'ziying'
__date__ = '2020/11/10 13:46'
__function__ = 'xxx'
"""

import re
import os
import sys
import time
import time
import json
import traceback


# from ceshi.leifu.lei import RsiOj


def wrapper(func):  # 装饰器函数
    def inner(*args, **kwargs):
        # print args, kwargs
        start_time = time.time()
        res = func(*args, **kwargs)  # 函数带有返回值
        end_time = time.time()
        print("函数运行所花费时间为: {}".format(end_time - start_time))
        return res

    return inner


@wrapper
def func(*args, **kwargs):
    try:
        pass
    except Exception as error:
        print('error message: %s %s' % (error.message, traceback.print_tb(error)))
    else:
        pass
    finally:
        pass


def main():
    func(1, 2, [3, 4], (5, 6), 'a', a=1, b=2)


class A(object):
    def __init__(self, name):
        self.name = name
        self.age = 6
        print("name..a:", self.name)

    def getName(self):
        return 'A ' + self.name


class B(A):
    dog_count = 0  # 定义类属性

    def __init__(self, name):
        super(B, self).__init__(name)  # 为了能使用或扩展父类的行为，最好显示调用父类的__init__方法
        self.name = name + '..b'
        self.age = 7
        self.food = 'apple'

    def getName(self):
        print(B.dog_count)

        B.get_info('876')
        B.drink('123')

        return 'B ' + self.name

    def eat(self):  # 对象方法
        print("吃{}".format(self.food))

    def run(self):
        self.getName()

    @classmethod
    def get_info(cls, b):  # 类方法使用场景： 不适用对象属性/方法， 但是使用类属性/类方法； 调用： 类名.类方法名
        print('%s dog count is : %s' % (b, B.dog_count))

    @staticmethod
    def drink(a):  # 静态方法默认情况下既不传递，也不传递对象； 调用： 类名/对象名.静态方法名
        print('喝水 %s' % a)


if __name__ == '__main__':
    main()
    # b = B('hello')
    # print b.getName()
    print(B('hello').run())
    func()
