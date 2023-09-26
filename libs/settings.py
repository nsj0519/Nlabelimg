# -*- coding: utf-8 -*-
import pickle
import os
import sys

#序列化与反序列化：序列化是通过pickle包中的dump，将数据写入到pkl文件当中，反序列化是通过load方法将序列化pkl文件按先进先出的顺序给读出来。
class Settings(object):
    def __init__(self):
        # Be default, the home will be in the same folder as labelImg,默认情况下，home将与labelImg在同一个文件夹中
        home = os.path.expanduser("~")#返回当前用户路径C:\Users\Reconova
        self.data = {}#声明一个对象属性data，存放.labelImgSettings.pkl反序列化出来的信息
        self.path = os.path.join(home, '.labelImgSettings.pkl')

    def __setitem__(self, key, value):#当data赋值操作时调用setitem方法
        self.data[key] = value

    def __getitem__(self, key):#通过对象[属性]即可调用getitem方法返回值
        return self.data[key]

    def get(self, key, default=None):#除了上述的__getitem__外这个方法也是用来获取设置信息(.labelImgSettings.pkl反序列化出来的信息)的参数的，如果有key这个参数就返回这个参数，如果没有这个参数那么就返回defult
        if key in self.data:
            return self.data[key]
        return default
    def pop(self,key):
        self.data.pop(key)
    def save(self):#用于保存设置信息的
        if self.path:
            with open(self.path, 'wb') as f:
                pickle.dump(self.data, f, pickle.HIGHEST_PROTOCOL)
                return True
        return False

    def load(self):#反序列化.labelImgSettings.pkl文件信息到self.data
        try:
            if os.path.exists(self.path):
                with open(self.path, 'rb') as f:
                    self.data = pickle.load(f)
                    return True
        except:
            print('Loading setting failed')#载入设置失败
        return False

    def reset(self):#重置配置信息，删除配置文件(用户目录下的.labelImgSettings.pkl文件)
        if os.path.exists(self.path):
            os.remove(self.path)
            print('Remove setting pkl file ${0}'.format(self.path))
        self.data = {}
        self.path = None
