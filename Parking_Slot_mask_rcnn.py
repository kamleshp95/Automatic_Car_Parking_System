import os
import sys
import random
import math
import numpy as np
import skimage.io
import matplotlib
import matplotlib.pyplot as plt
import pickle
import coco
import pdb
import cv2 
import pandas as pd
import numpy as np
import gc
from tqdm import tqdm_notebook as tqdm
from datetime import datetime

from mrcnn import utils
import mrcnn.model as modellib
from mrcnn import visualize
from utilities import assign_next_frame ,get_data

ROOT_DIR = os.path.abspath("./")
sys.path.append(ROOT_DIR)  # To find local version of the library
sys.path.append(os.path.join(ROOT_DIR, "samples/coco/"))  # To find local version
MODEL_DIR = os.path.join(ROOT_DIR, "logs")
COCO_MODEL_PATH = os.path.join(ROOT_DIR, "mask_rcnn_coco.h5")
if not os.path.exists(COCO_MODEL_PATH):
    utils.download_trained_weights(COCO_MODEL_PATH)
IMAGE_DIR = os.path.join(ROOT_DIR, "images")

class InferenceConfig(coco.CocoConfig):
    GPU_COUNT = 1
    IMAGES_PER_GPU = 1
class_names = ['BG', 'person', 'bicycle', 'car', 'motorcycle', 'airplane',
    'bus', 'train', 'truck', 'boat', 'traffic light',
    'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird',
    'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear',
    'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie',
    'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
    'kite', 'baseball bat', 'baseball glove', 'skateboard',
    'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup',
    'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
    'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
    'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed',
    'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
    'keyboard', 'cell phone', 'microwave', 'oven', 'toaster',
    'sink', 'refrigerator', 'book', 'clock', 'vase', 'scissors',
    'teddy bear', 'hair drier', 'toothbrush']



# ! mkdir ./movie
# ! mkdir ./movie/tmp
# ! mkdir ./movie/train
# ! mkdir ./movie/test

# TRAIN_MOVIE = "./movie/train/"
# TEST_MOVIE = "./movie/test/"
# TMP_MOVIE ="./movie/tmp"


def create_boxes(images, model, verbose = 0 ,  plot = False):
  data  = pd.DataFrame()
  masks = []
  for i in range(len(images)):
    image = skimage.io.imread(images[i])
    results = model.detect([image], verbose=verbose)
    r = results[0]
    if r['rois'].shape[0] > 0 :
      if plot: 
        visualize.display_instances(image, r['rois'], r['masks'], r['class_ids'], 
                                  class_names, r['scores'])
      df  = pd.DataFrame(r['rois'] , columns =["y1","x1","y2","x2"])
      df["score"] = r['scores']
      df["class"] =r['class_ids']
      df["frame"] = i
      df["labels"] = np.arange(len(df))
      df = df[df["class"] ==3 ]
      masks.append(r['masks'][:,:,r['class_ids'] ==3])
      data = data.append(df, ignore_index=True)
    else :
      print(images[i], "NO BOUNDING BOX DETECTED")
    
  data["xc"] = (data["x1"] + data["x2"])/2
  data["yc"] = (data["y1"] + data["y2"])/2
  data["w"] =  data["x2"] -data["x1"]
  data["b"] = data["y2"] - data["y1"]
  data["a"] = data["b"]*data["w"] 
  data = data[["labels", 'x1', 'y1', 'x2', 'y2',  'xc', 'yc', 'w',  'a' , 'b', 'score', 'class', 'frame' ]]
  return data ,  masks



def compute_distance(df, image, th = 0.92, label = "Parking Slots", plot = False):
  df.reset_index(drop=True, inplace=True)
  n =  len(df)
  base_col = ['x1', 'y1', 'x2', 'y2',  'xc', 'yc', 'w' , 'b']
  df.reset_index(drop=True, inplace=True)
  mat, _, _, _ = assign_next_frame(df, df, th = 0.6)
  np.fill_diagonal(mat, -9)
  mat = np.tril(mat)
  count = n
  to_merge = []
  while count > 0:
    r,k = np.unravel_index(np.argmax(mat, axis=None), mat.shape)
    if mat[r,k] > th :
      to_merge.append([r,k])

    mat[r,:] = -9
    mat[:,k] = -9
    mat[k,:] = -9
    mat[:,r] = -9
    count = count -1
#   print(to_merge)
  for i in range(len(to_merge)):
    r = to_merge[i][0]
    k = to_merge[i][1]
    df.loc[r,base_col] =(df.loc[r,base_col] * df.loc[r,"found"] +  df.loc[r,base_col]* df.loc[k,"found"])/(df.loc[r,"found"]+df.loc[k,"found"])
    df.at[r,"found"] =  df.at[r,"found"]+ df.at[k,"found"]
    df.drop(k, axis=0, inplace = True)
  if plot :
    visualize.display_instances(image, df[["y1","x1","y2","x2"]].values,\
                      None, df["class"].values, class_names,
                      scores=None, title=label,
                      figsize=(16, 16), ax=None,
                      show_mask=False, show_bbox=True,
                      colors=None, captions=df["labels"].astype(str).values)
  return df

pd.options.mode.chained_assignment = None

def look_for_slots(data,  img=[],PRUNE_TH = 3, 
                                ASSIGN_TH =  0.6,
                                plot = True,
                                PRUNE_STEP =  10,
                                MERGE_STEP =  20,
                                MERGE_TH =  0.75):
  
  
  n_fr = data["frame"].nunique()
  cols = ["labels", 'x1', 'y1', 'x2', 'y2',  'xc', 'yc', 'w' , 'b','a',"class" ]
  base_col = ['x1', 'y1', 'x2', 'y2',  'xc', 'yc', 'w' , 'b','a']
  slots  = data[data["frame"] == 0 ][cols]
  slots["found"] = 1
  
#   out_boxes,  out_classes, found, labels
# "empty":"#4a148c","occupy":"#f44336", "new":"#7cb342","del":"#80deea" 
  print("LOOKING FOR PARKING SLOTS INSIDE IMAGE FRAMES")
  for i in  tqdm(range(1 ,n_fr)) : 
    post =  data[data["frame"]==i].reset_index(drop=True)
    _,iou, id_map, status = assign_next_frame(slots, post, th = ASSIGN_TH)
    #print(id_map.keys(), status.sum())
    
    ## found again
    mask = post["labels"].isin(id_map.keys())
    
    slots.loc[status,"found"] = slots.loc[status,"found"] +1
    occupy =  post[mask]
    occupy["labels"] = occupy["labels"].map(id_map)
    
    slots.sort_values(by =["labels"] , inplace=True)
    slots.reset_index(drop=True, inplace=True)
    occupy.sort_values(by =["labels"], inplace = True)
    occupy.reset_index(drop=True, inplace=True)
    slots.loc[status,base_col] = slots.loc[status,base_col].values *(1 - 1/(i+1)) +  occupy[base_col].values/(i+1)
     
    # clean up
    if i % PRUNE_STEP ==0 :
      slots.drop(slots[slots["found"] < PRUNE_TH+1].index, inplace=True) 
      #print(slots)

    # merge 
    if i % MERGE_STEP ==0 :
      
      slots = compute_distance(slots, img[i-1], th = MERGE_TH, label = "Parking Slots "+ str(i))
       
    # new
    idx = np.logical_not(post["labels"].isin(id_map.keys()))
    new  =  post[idx]
    new["labels"] =  new["labels"] + slots["labels"].max() + 1
    new  = new[cols]
    if len(new ) > 0 :
      new["found"] = 1
    slots = slots.append(new,  sort=True).reset_index(drop=True) 
    if plot | (i % MERGE_STEP ==0):
      df = slots[['x1', 'y1', 'x2', 'y2',"found","labels" ]].copy()
#       colors = [(0,1,0)]*len(df)
      msk = df["labels"].isin(id_map.values())
      
      colors = [ (1,0,0) if ms else (0,1,0)   for ms in msk  ]
#       df.loc[msk,["R","G","B"]] =np.array([(1,0,0)]*msk.sum())
      nw_df = new[['x1', 'y1', 'x2', 'y2',"labels" ]].copy()
      colors   =  colors +   [(0,1,0)]*len(nw_df)
      nw_df["found"]=1 
      df = df.append(nw_df,  sort=True).reset_index(drop=True)
      df["captions"] = df["labels"].astype(str) + " [" +df["found"].astype(str) + "]"

        
        
#       pdb.set_trace()
      masks =  np.empty((4,4,len(df)))
      class_ids = np.array([3]*len(df))
      captions = df["captions"].tolist()
      visualize.display_instances(cv2.imread(img[i]), 
                   df[["y1","x1","y2","x2"]].values,\
                  masks, class_ids, None,
                scores=None, title=img[i],
                figsize=(20, 20), ax=None,
                show_mask=False, show_bbox=True,
                colors=colors, 
                      captions=captions)
    
  slots.drop(slots[slots["found"] < PRUNE_TH*3].index, inplace=True) 
  slots = compute_distance(slots, img[0], th = MERGE_TH*0.8, label = "Parking Slots "+ str(MERGE_STEP))
  print(len(slots), "SLOTS FOUND")
  return slots




image_data =  get_data()

config = InferenceConfig()
config.DETECTION_MIN_CONFIDENCE = 0.8
config.display()
# Create model object in inference mode.
model = modellib.MaskRCNN(mode="inference", model_dir=MODEL_DIR, config=config)

# Load weights trained on MS-COCO
model.load_weights(COCO_MODEL_PATH, by_name=True)

for camera  in  image_data["camera"].unique():
  images =  image_data[image_data["camera"] == camera ]["path"].values
  images = np.sort(images)

  img_train = images[:21]
  img_pred = images[len(images) // 2:len(images) // 2 +2]
  park_data,masks =  create_boxes(img_train, model)
  park_slots = look_for_slots(park_data,  img= img_train,plot =False,
                    PRUNE_TH = 1,
                    ASSIGN_TH =  0.6,
                    PRUNE_STEP =  10,
                    MERGE_STEP =  20,
                    MERGE_TH =  0.7)
  park_slots.drop(park_slots[park_slots["found"] < 3].index, inplace=True) 
  park_slots=compute_distance(park_slots, images[20], th=0.2,  label ="20")
  park_slots[['x1', 'y1', 'x2', 'y2',  'xc', 'yc', 'w' , 'b', "found"]] = park_slots[['x1', 'y1', 'x2', 'y2',  'xc', 'yc', 'w' , 'b', "found"]].astype(int)
  park_slots= park_slots.reset_index(drop=True)
  park_slots.to_csv("./parkings/"+camera+".csv", index = False)


