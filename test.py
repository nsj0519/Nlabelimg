import re
import time

import cv2


# pointlist = [(1.7187488079071045,608.1114196777344),(371.7187488079071,518.1114196777344),(540.4687488079071,480.6114196777344),(304.2187488079071,715.6114196777344),(497.9687488079071,549.3614196777344),(571.7187488079071,483.1114196777344),(934.2187488079071,714.3614196777344),(721.7187488079071,550.6114196777344),(634.2187488079071,481.8614196777344),(1270.468748807907,635.6114196777344),(817.9687488079071,521.8614196777344),(662.9687488079071,483.1114196777344)]
# point_color = (255, 0, 255)
# point_size = 1
# thickness = 2
# img = cv2.imread(r"E:\labelImg-master\demo2\test1\1669281744777.jpg")

# for Z in pointlist:
#     x = int(Z[0])
#     y = int(Z[1])
#     pos = (x,y)
#     cv2.circle(img,pos,point_size,point_color,thickness)
#     cv2.imshow("img", img)  # 展示结果
#     cv2.waitKey(2000)  # 展示多久后关闭。4000=4秒
#     cv2.destroyAllWindows()

# label_path = r"E:/labelImg-master/demo2/test1/data.label"
# with open(label_path,"r",encoding="utf-8") as file:
#     label_lines = file.readlines()
# for label in label_lines:
#     print(label)
#     pointList = label.split("\t")[1]
#     print(re.findall(r";(.+?)\)", pointList,re.M))
    # for point in pointList:
    #     print(re.findall(r",(.*)\)", point))
    # label_xy = label.split(" ")[]

list = ["1","2"]

print(",".join(list))