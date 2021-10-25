import torch.utils.data as data
from PIL import Image
import os
import os.path
import errno
import torch
import json
import codecs
import numpy as np
import sys
import torchvision.transforms as transforms
import argparse
import json
import time
import random
import numpy.ma as ma
import copy
import scipy.misc
import scipy.io as scio
import yaml
import cv2
import open3d as o3d ## OPEN3D ??

train_obj_num = 20## we use 20 obj from train_list_sort for training
test_obj_num = 10##

class PoseDataset(data.Dataset):
    def __init__(self, mode, num, add_noise, root, noise_trans, refine):
        self.mode = mode

        self.list_rgb = []
        self.list_depth = []
        self.list_label = []
        self.list_obj = []
        self.list_rank = []
        self.meta = {}
        self.pt = {}
        self.list_pcd = []
        self.root = root
        self.noise_trans = noise_trans
        self.refine = refine
        self.obj_list = []

        # if self.mode == 'train':
        #     with open(f"{self.root}/train_list_sort.txt", 'r') as f:
        #         for _ in range(train_obj_num):
        #             self.obj_list.append(int(f.readline().strip()))
        # else:
        #     with open(f"{self.root}/test_list_sort.txt", 'r') as f:
        #         for _ in range(test_obj_num):
        #             self.obj_list.append(int(f.readline().strip()))
        # load the index of file from train_list_sort 
        with open(f"{self.root}/train_list_sort.txt", 'r') as f: ### f-string
                for _ in range(train_obj_num):
                    self.obj_list.append(int(f.readline().strip()))## remove spaces around the index string
        
        image_idx = [i for i in range(100)]

        item_count = 0
        # train: obj up to 110, test: obj up to 40   
        for item in self.obj_list: ## 20 objects from 100 images(or folders?)
            poses = {}
            for idx in image_idx:
                item_count += 1
                if self.mode == 'test' and item_count % 10 != 0:
                    continue

                self.list_rgb.append(f'{self.root}/train/exr/{item}/clr/{idx}.png')      ## there is no /clr directories? all files are .exr, instead of .png??
                self.list_depth.append(f'{self.root}/train/depth/{item}/{idx}.png')      ## relationship between item file and idx file? or ,object and rank?
                self.list_label.append(f'{self.root}/train/exr/{item}/mask/{idx}.png')      ## no mask? label is png?
                
                self.list_obj.append(item)
                self.list_rank.append(idx)

                idx_gt = np.loadtxt(f'{self.root}/train/pose/{item}/{idx}.txt')        ## so this is the ground truth RT matrix? if so, what about self.list_label?
                poses[idx] = {'cam_R_m2c': idx_gt[:3,:3].reshape(9).tolist(), 'cam_t_m2c': np.rad2deg(idx_gt[:3,3].reshape(3)).tolist()}   ## rotation and translation both 3x3?
                self.list_pcd.append(f'{self.root}/train/pcd/{item}/{idx}.pcd')
                                                                                        ## relationship between those .png, .pcd?
            self.meta[item] = poses                                                     ## what is meta?
            
            print("Object {0} buffer loaded".format(item))

        self.length = len(self.list_rgb)

        self.cam_cx = 320
        self.cam_cy = 240
        self.cam_fx = 320
        self.cam_fy = 320

        self.xmap = np.array([[j for i in range(640)] for j in range(480)])
        self.ymap = np.array([[i for i in range(640)] for j in range(480)])
        
        self.num = num
        self.add_noise = add_noise
        self.trancolor = transforms.ColorJitter(0.2, 0.2, 0.2, 0.05)
        self.norm = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        self.border_list = [-1, 40, 80, 120, 160, 200, 240, 280, 320, 360, 400, 440, 480, 520, 560, 600, 640, 680]
        self.num_pt_mesh_large = 1000
        self.num_pt_mesh_small = 1000                                                   ## why change it from 500 to 1000?
        self.symmetry_obj_idx = self.obj_list.copy()                                    ## all symetry?

    def __getitem__(self, index):
        img = Image.open(self.list_rgb[index])
        ori_img = np.array(img)
        depth = np.array(Image.open(self.list_depth[index]))
        label = np.array(Image.open(self.list_label[index]))
        obj = self.list_obj[index]
        rank = self.list_rank[index] # rank represents idx in the init function above      

        # if obj == 2:
        #     for i in range(0, len(self.meta[obj][rank])):
        #         if self.meta[obj][rank][i]['obj_id'] == 2:
        #             meta = self.meta[obj][rank][i]
        #             break
        # else:
        meta = self.meta[obj][rank]

        mask_depth = ma.getmaskarray(ma.masked_not_equal(depth, 0))                     # mask non zero values as invalid. means we are only caring about the 0 class?
        if self.mode == 'eval':
            mask_label = ma.getmaskarray(ma.masked_equal(label, np.array(255)))         
        else:
            mask_label = ma.getmaskarray(ma.masked_equal(label, np.array([255, 255, 255])))[:, :, 0]   # why make it an np array? why throw 255 away?
        
        mask = mask_label * mask_depth                                                  # why multiply label??

        if self.add_noise:
            img = self.trancolor(img)

        img = np.array(img)[:, :, :3]
        img = np.transpose(img, (2, 0, 1))
        img_masked = img

        # if self.mode == 'eval':
        #     rmin, rmax, cmin, cmax = get_bbox(mask_to_bbox(mask_label))
        # else:
        #     rmin, rmax, cmin, cmax = get_bbox(meta['obj_bb'])

        # current do not have obj_bb info
        rmin, rmax, cmin, cmax = get_bbox(mask_to_bbox(mask_label))

        img_masked = img_masked[:, rmin:rmax, cmin:cmax] ## crop the image in bounding box
        #p_img = np.transpose(img_masked, (1, 2, 0))
        #scipy.misc.imsave('evaluation_result/{0}_input.png'.format(index), p_img)

        target_r = np.resize(np.array(meta['cam_R_m2c']), (3, 3))
        target_t = np.array(meta['cam_t_m2c'])
        add_t = np.array([random.uniform(-self.noise_trans, self.noise_trans) for i in range(3)])

        choose = mask[rmin:rmax, cmin:cmax].flatten().nonzero()[0]
        if len(choose) == 0:
            cc = torch.LongTensor([0])
            return(cc, cc, cc, cc, cc, cc)

        if len(choose) > self.num:                                                     #randomly pick self.num points from masked depth image?
            c_mask = np.zeros(len(choose), dtype=int)
            c_mask[:self.num] = 1
            np.random.shuffle(c_mask)
            choose = choose[c_mask.nonzero()]
        else:
            choose = np.pad(choose, (0, self.num - len(choose)), 'wrap')
        
        depth_masked = depth[rmin:rmax, cmin:cmax].flatten()[choose][:, np.newaxis].astype(np.float32)
        xmap_masked = self.xmap[rmin:rmax, cmin:cmax].flatten()[choose][:, np.newaxis].astype(np.float32)
        ymap_masked = self.ymap[rmin:rmax, cmin:cmax].flatten()[choose][:, np.newaxis].astype(np.float32)
        choose = np.array([choose])

        cam_scale = 1.0
        pt2 = depth_masked / cam_scale
        pt0 = (ymap_masked - self.cam_cx) * pt2 / self.cam_fx
        pt1 = (xmap_masked - self.cam_cy) * pt2 / self.cam_fy
        cloud = np.concatenate((pt0, pt1, pt2), axis=1)
        cloud = cloud / 1000.0                                                          # why divided by 1000?

        if self.add_noise:
            cloud = np.add(cloud, add_t)

        #fw = open('evaluation_result/{0}_cld.xyz'.format(index), 'w')
        #for it in cloud:
        #    fw.write('{0} {1} {2}\n'.format(it[0], it[1], it[2]))
        #fw.close()


        # model_points = self.pt[obj] / 1000.0
        pcd = o3d.io.read_point_cloud(self.list_pcd[index]) 
        model_points = np.asarray(pcd.points) 
        dellist = [j for j in range(0, len(model_points))]
        dellist = random.sample(dellist, len(model_points) - self.num_pt_mesh_small)
        model_points = np.delete(model_points, dellist, axis=0)

        #fw = open('evaluation_result/{0}_model_points.xyz'.format(index), 'w')
        #for it in model_points:
        #    fw.write('{0} {1} {2}\n'.format(it[0], it[1], it[2]))
        #fw.close()

        target = model_points # these should be transformed points already
        # target = np.dot(model_points, target_r.T)
        # if self.add_noise:
        #     target = np.add(target, target_t / 1000.0 + add_t)
        #     out_t = target_t / 1000.0 + add_t
        # else:
        #     target = np.add(target, target_t / 1000.0)
        #     out_t = target_t / 1000.0

        #fw = open('evaluation_result/{0}_tar.xyz'.format(index), 'w')
        #for it in target:
        #    fw.write('{0} {1} {2}\n'.format(it[0], it[1], it[2]))
        #fw.close()

        return torch.from_numpy(cloud.astype(np.float32)), \
               torch.LongTensor(choose.astype(np.int32)), \
               self.norm(torch.from_numpy(img_masked.astype(np.float32))), \
               torch.from_numpy(target.astype(np.float32)), \
               torch.from_numpy(model_points.astype(np.float32)), \
               torch.LongTensor([self.obj_list.index(obj)])

    def __len__(self):
        return self.length

    def get_sym_list(self):
        return self.symmetry_obj_idx

    def get_num_points_mesh(self):
        if self.refine:
            return self.num_pt_mesh_large
        else:
            return self.num_pt_mesh_small



border_list = [-1, 40, 80, 120, 160, 200, 240, 280, 320, 360, 400, 440, 480, 520, 560, 600, 640, 680]
img_width = 480
img_length = 640


def mask_to_bbox(mask):
    mask = mask.astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)


    x = 0
    y = 0
    w = 0
    h = 0
    for contour in contours:
        tmp_x, tmp_y, tmp_w, tmp_h = cv2.boundingRect(contour)
        if tmp_w * tmp_h > w * h:
            x = tmp_x
            y = tmp_y
            w = tmp_w
            h = tmp_h
    return [x, y, w, h]


def get_bbox(bbox):
    bbx = [bbox[1], bbox[1] + bbox[3], bbox[0], bbox[0] + bbox[2]]
    if bbx[0] < 0:
        bbx[0] = 0
    if bbx[1] >= 480:
        bbx[1] = 479
    if bbx[2] < 0:
        bbx[2] = 0
    if bbx[3] >= 640:
        bbx[3] = 639                
    rmin, rmax, cmin, cmax = bbx[0], bbx[1], bbx[2], bbx[3]
    r_b = rmax - rmin
    for tt in range(len(border_list)):
        if r_b > border_list[tt] and r_b < border_list[tt + 1]:
            r_b = border_list[tt + 1]
            break
    c_b = cmax - cmin
    for tt in range(len(border_list)):
        if c_b > border_list[tt] and c_b < border_list[tt + 1]:
            c_b = border_list[tt + 1]
            break
    center = [int((rmin + rmax) / 2), int((cmin + cmax) / 2)]
    rmin = center[0] - int(r_b / 2)
    rmax = center[0] + int(r_b / 2)
    cmin = center[1] - int(c_b / 2)
    cmax = center[1] + int(c_b / 2)
    if rmin < 0:
        delt = -rmin
        rmin = 0
        rmax += delt
    if cmin < 0:
        delt = -cmin
        cmin = 0
        cmax += delt
    if rmax > 480:
        delt = rmax - 480
        rmax = 480
        rmin -= delt
    if cmax > 640:
        delt = cmax - 640
        cmax = 640
        cmin -= delt
    return rmin, rmax, cmin, cmax


def ply_vtx(path):
    f = open(path)
    assert f.readline().strip() == "ply"
    f.readline()
    f.readline()
    N = int(f.readline().split()[-1])
    while f.readline().strip() != "end_header":
        continue
    pts = []
    for _ in range(N):
        pts.append(np.float32(f.readline().split()[:3]))
    return np.array(pts)
