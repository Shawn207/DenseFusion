

import os
import sys
from IPython import embed  ## what is that used for
import open3d as o3d
import Imath
import OpenEXR
import Image                                ## deal with PIL image
import numpy as np
import cv2

pair = {}
with open('name_value.txt','r') as f:       ## read only
    for line in f.readlines():
        line = line.split()
        pair[line[0]] = (int)(line[1])      ## a dictionary mappring from key: name of image to value:index of image. Wait, is that image? or folder?


num_sub = len(pair)
if num_sub != 150:
    embed()                                 ## what is that?


origin_idr = os.getcwd()

##################################
# we have several similar file architecture: foldre_path--fold--file. The name of folds are
# extremely complex and strange so we use this fucntion to change its name to our selfdefined indcies
##################################

def ChangeSubFolder(folder_path):
    target_list = os.listdir(folder_path)
    if len(target_list) != num_sub:         ## to ensure the number of name-value pair in naem_value.txt is the same as real situation 
        embed()                             ## again
        return
    
    try: 
        os.chdir(folder_path)               ## change cwd to folder_path                                           
    except:                                  ## why put it in a try-except block?
        return 

    for fold in target_list:                ## for every fold in folder_path
        if fold not in pair:
            continue
        os.mkdir(f"{pair[fold]}")           ## make a dir for each index corresponding to fold
        for file in os.listdir(fold):       ## for each for in folder_Path--fold--file
            os.renames(os.path.join(os.getcwd(),f'{fold}/{file}'), os.path.join(os.getcwd(),f'{pair[fold]}/{file}'))## not that a path of dir end up with '/'
    os.chdir(origin_idr)

##############################
# similar as the above function. this time, we have some files in a dir with strange name and we also wanna change it to indcies
##############################

def ChangeCompleteFileName(folder_path):
    target_list = os.listdir(folder_path)
    if len(target_list) != num_sub:
        return 
    try: 
        os.chdir(folder_path)               ## change cwd to folder_path                                           
    except:                                  
        return 
    
    for file in target_list:
        prefix = file.split('.')[0]         ## prefix of file name: the name of file
        os.renames(os.path.join(os.getcwd(),f"{prefix}.pcd"),os.path.join(os.getcwd(),f'{pair[prefix]}.pcd'))
    os.chdir(origin_idr)

#############################
# generating mask? mask is .exr?
#############################
def generate_mask(exrfile,jpgfile):
    file = OpenEXR.InputFile(exrfile)
    pt = Imath.PixelType(Imath.PixelType.FLOAT)
    dw = file.header()['dataWindow']
    size = (dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1) 
    
    rgbf = [Image.frombytes("F",size,file.channel(c,pt)) for c in "RGB"] ## read and copy each 3 channels in a rgb file

    extrema = [im.getextrema() for im in rgbf] ## get the min/max value of pixel for each channel
    darkest = min([lo for (lo,hi) in extrema])
    lighest = max([hi for (lo,hi) in extrema]) 
    scale = 255/(lighest-darkest)
    def normalize_0_255(v):                 ## Does this normalize to 0-255?
        return (v*scale) + darkest
    rgb8 = [im.point(normalize_0_255).convert("L") for im in rgbf]## conver to grayscale
    Image.merge("RGB", rgb8).save(jpgfile+'.jpg') 
    cv2.imwrite(jpgfile+'.png', 255 * np.array(Image.open(jpgfile+'.jpg')))    ## why png?



# used for generating mask
# for i in range(150): 
#     os.chdir(f"{i}") 
#     if not os.path.exists("mask"): 
#         os.mkdir("mask") 
#     for j in range(100): 
#         generate_mask(f"{origin_pwd}/{i}/{j}.exr", f"{origin_pwd}/{i}/mask/{j}") 
#     os.chdir(origin_pwd) 

# change the name of pointcloud files in complete dir
# ChangeCompleteFileName('complete')

ChangeSubFolder('train/depth/02691156')
ChangeSubFolder('train/exr/02691156')
ChangeSubFolder('train/pcd/02691156')
ChangeSubFolder('train/pose/02691156')
