# /usr/lib/python3

import os
import sys
from IPython import embed
import open3d as o3d
import Imath
import OpenEXR
import Image
import numpy as np
import cv2

pair = {}
with open('name_value.txt', 'r') as f:
    for line in f.readlines():
        line = line.split()
        pair[line[0]] = (int)(line[1])



num_sub = len(pair)
if num_sub != 150:
    embed()

origin_dir = os.getcwd()

def ChangeSubFolder(folder_path):
    target_list = os.listdir(folder_path)
    if len(target_list) != num_sub:
        embed()
        return

    try:
        os.chdir(folder_path)
    except:
        return

    for fold in target_list:
        if fold not in pair:
            continue
        os.mkdir(f"{pair[fold]}")
        for file in os.listdir(fold):
            os.renames(os.path.join(os.getcwd(), f'{fold}/{file}'), os.path.join(os.getcwd(), f'{pair[fold]}/{file}'))
        # os.rmdir(fold)
    os.chdir(origin_dir)

def ChangeCompleteFileName(folder_path):
    target_list = os.listdir(folder_path)
    if len(target_list) != num_sub:
        return

    try:
        os.chdir(folder_path)
    except:
        return

    for file in target_list:
        prefix = file.split('.')[0]
        os.renames(os.path.join(os.getcwd(), f"{prefix}.pcd"), os.path.join(os.getcwd(), f'{pair[prefix]}.pcd'))
    os.chdir(origin_dir)


def generate_mask(exrfile, jpgfile): 
    file = OpenEXR.InputFile(exrfile) 
    pt = Imath.PixelType(Imath.PixelType.FLOAT) 
    dw = file.header()['dataWindow'] 
    size = (dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1) 
    
    rgbf = [Image.frombytes("F", size, file.channel(c, pt)) for c in "RGB"] 
    
    extrema = [im.getextrema() for im in rgbf] 
    darkest = min([lo for (lo,hi) in extrema]) 
    lighest = max([hi for (lo,hi) in extrema]) 
    scale = 255 / (lighest - darkest) 
    def normalize_0_255(v): 
        return (v * scale) + darkest 
    rgb8 = [im.point(normalize_0_255).convert("L") for im in rgbf] 
    Image.merge("RGB", rgb8).save(jpgfile+'.jpg') 
    cv2.imwrite(jpgfile+'.png', 255 * np.array(Image.open(jpgfile+'.jpg'))) 

# used for generating mask
# for i in range(150): 
#     os.chdir(f"{i}") 
#     if not os.path.exists("mask"): 
#         os.mkdir("mask") 
#     for j in range(100): 
#         generate_mask(f"{origin_pwd}/{i}/{j}.exr", f"{origin_pwd}/{i}/mask/{j}") 
#     os.chdir(origin_pwd) 

# ChangeCompleteFileName('complete')


ChangeSubFolder('train/depth/02691156')
ChangeSubFolder('train/exr/02691156')
ChangeSubFolder('train/pcd/02691156')
ChangeSubFolder('train/pose/02691156')
