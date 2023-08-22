import os
import time
import re
from tkinter.messagebox import *
import xml.etree.ElementTree as ET
from tkinter import *
from tkinter import messagebox
from tkinter import filedialog
from PIL import ImageTk,Image

class tool():
    def __init__(self):
        self.root = Tk()
        self.root.title(r"标签统计工具v1.0.0")
        self.w = int(self.root.winfo_screenwidth() * 0.4)
        self.h = int(self.root.winfo_screenheight() * 0.6)
        self.root.geometry("%dx%d+%d+%d" % (self.w, self.h, 0, 0))  # 设置窗口大小为全屏c
        self.root.resizable(width=False, height=False)  # 设置窗口宽高不可拉升

        self.fm1 = Frame(self.root, background="#808080")  # 统计标注文件类型选择区域
        self.fm1.place(x=0, y=0, width=170, height=self.h)

        self.fm2 = Frame(self.root, background="#e8dce2")  # 选择文件展示统计结果区域
        self.fm2.place(x=170, y=0, width=self.w - 170, height=self.h)

        self.radiolist = [["Box—Xml", 0], ["Lane—Lable", 1]]
        self.var1 = IntVar()
        for i in self.radiolist:
            self.radio = Radiobutton(self.fm1, text=i[0], background="#808080",variable=self.var1,value=i[1])
            self.radio.pack(pady=20, side=TOP)
        self.v1 = StringVar()
        self.v1.set("")

        self.labelNumText = StringVar()
        self.labelboxNumText = StringVar()
        self.labelNum = 0
        self.labelboxNum = 0
        self.labelNumText.set(f"标注文件共：{self.labelNum}")
        self.labelboxNumText.set(f"标签数量共：{self.labelboxNum}")

        self.subbut = Frame(self.fm2, background="#e8e0e0", highlightbackground="black", highlightthickness=1)
        self.subbut.place(x=0, y=0, width=self.w - 170, height=80)
        self.ent = Entry(self.subbut, textvariable=self.v1, font=("宋体", 10)).place(relx=0.06, rely=0.2, relwidth=0.7,relheight=0.6)  # 输入路径
        self.fileButton = Button(self.subbut, text="选择目录", command=self.opendir).place(relx=0.76, rely=0.2, relwidth=0.2,relheight=0.6)  # 选择文件夹按钮

        self.showbox = Frame(self.fm2, background="#e8dce2", highlightbackground="black", highlightthickness=1)
        self.showbox.place(x=0, y=80, width=self.w - 170, height=self.h - 80)
        self.action = Button(self.showbox, text="开始统计", command=self.statistics).place(relx=0.4, rely=0.1, relwidth=0.2,relheight=0.1)  # 选择文件夹按钮
        self.LabelNum_line = Label(self.showbox,background="#ffffff", textvariable=self.labelNumText).place(relx=0, rely=0.3, relwidth=1, relheight=0.1)
        self.LabelboxNum_line = Label(self.showbox,background="#ffffff", textvariable=self.labelboxNumText).place(relx=0, rely=0.4, relwidth=1,relheight=0.1)
        self.root.mainloop()


    def opendir(self):
        if self.var1.get() == 0:
            dir_path = filedialog.askdirectory()
            if dir_path:
                self.v1.set(dir_path)
        elif self.var1.get() == 1:
            dir_path = filedialog.askopenfilename()
            if dir_path:
                self.v1.set(dir_path)

    # 解析画框的xml标注文件
    def analysis_xml(self,file_path):
        tree = ET.parse(file_path)
        root = tree.getroot()
        Labellist = root.findall("object")
        return len(Labellist)

    # 解析车道线标注label文档
    def analysis_label(self,file_path):

        with open(file_path,"r",encoding="utf-8") as label:
            label_lines = label.readlines()
        for label_line in label_lines:
            D = 0
            newlist = []
            self.labelNum += 1
            pointList = label_line.split("\t")[1]
            point_xy = re.findall(r";(.+?)\)", pointList, re.M)
            for point_id in range(len(point_xy)-1):
                if int(float(point_xy[point_id]))-int(float(point_xy[point_id+1])) <=0:#得出每个点Y坐标的变化，突然变小说明是一条新的车道线。
                    newlist.append(point_xy[D:point_id+1])
                    D = point_id+1
                elif point_id+1 == len(point_xy)-1:
                    newlist.append(point_xy[D:point_id+2])
            self.labelboxNum += len(newlist)
            print(newlist)



    def getfiles(self,dir_path,format):
        if os.path.isdir(dir_path):
            filelist = os.listdir(dir_path)
            for filename in filelist:
                file_path = os.path.join(dir_path,filename)
                if os.path.isdir(file_path):
                    self.getfiles(file_path,format)
                elif os.path.isfile(file_path) and filename.split(".")[-1]=="xml" and format == 0:
                    self.labelNum +=1
                    Thislabelnum = self.analysis_xml(file_path)
                    self.labelboxNum += Thislabelnum

        elif os.path.isfile(dir_path) and dir_path.split(".")[-1]=="label" and format == 1:
            self.analysis_label(dir_path)
        self.labelNumText.set(f"标注文件共：{self.labelNum}")
        self.labelboxNumText.set(f"标签数量共：{self.labelboxNum}")



    def statistics(self):
        dir_path = self.v1.get()
        format = self.var1.get()
        self.getfiles(dir_path,format)
        showinfo('提示 ', '完成统计 ' )
        self.labelNum = 0
        self.labelboxNum = 0


tool()

