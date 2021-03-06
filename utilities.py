import numpy as np
from mrcnn import utils
import os
import pandas as pd

def assign_next_frame(prior, post, th = 0.7, pr =False):
  iou =np.zeros(len(prior))
  status =np.zeros(len(prior))
  iou_mat = np.zeros((len(prior), len(post)))
  for k in range(len(prior)) : 
    p = prior.loc[k,:]
    iou_mat[k,:] = utils.compute_iou( (p.y1,p.x1,p.y2,p.x2),\
                     post[["y1","x1","y2","x2"]].values,p.a, post["a"].values)
  #iou_mat =  np.tril(iou_mat)
  id_map ={}
  count =  min(len(prior), len(post))
  mat=np.copy(iou_mat)
  while count >0 :
    #pdb.set_trace()
    r,k  = np.unravel_index(np.argmax(iou_mat, axis=None), iou_mat.shape)
    if iou_mat[r,k] > th :
      id_map[post.at[k,"labels"]] =prior.at[r,"labels"]
      iou[r] = iou_mat[r,k]
      status[r]=1
    iou_mat[r,:] =  -99
    iou_mat[:,k] =  -99
    count = count -1
  return mat, iou, id_map, status.astype(bool)





def get_data():
  PATH = "./FULL_IMAGE_1000x750/"
  image_data  =  pd.DataFrame()#[],columns=["image","path","camera","date","condition"])
  conditions = ["SUNNY" , "RAINY", "OVERCAST"]
  dates = os.listdir(PATH)

  for condition in conditions :
    date_path   = PATH+condition+"/"
    dates  = os.listdir(date_path)
    for date in dates : 
      camera_path   = date_path+date+"/"
      cameras  = os.listdir(camera_path)
      for camera in cameras :
        #print(camera)
        images = os.listdir(camera_path+camera+"/")
        paths  =  [camera_path+camera+"/" +  image for image in images]
        d =  pd.DataFrame({"image" : images ,  "path": paths})
        d["camera"]  = camera
        d["date"] = date
        d["condition"] = condition
  #      print(d)
        image_data = image_data.append(d, ignore_index=True)
  image_data["camera"] = image_data["camera"].astype("category")
  image_data["date"] = image_data["date"].astype("category")
  image_data["condition"] = image_data["condition"].astype("category")
  return image_data
