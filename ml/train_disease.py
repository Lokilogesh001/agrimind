"""Train MobileNetV3-Large on the official PlantVillage color manifests.

Primary evaluation uses a leaf-grouped validation split made ONLY from the
provided training manifest. The official test manifest is touched only once
for the final report, avoiding test-set early-stopping leakage.
"""
from __future__ import annotations
import argparse, json, random
from pathlib import Path
import numpy as np
import torch
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from torch import nn
from torch.utils.data import DataLoader, Subset
from torchvision import transforms
from .disease_model import build_model, save_checkpoint
from .plantvillage_dataset import PlantVillageManifestDataset

IMAGENET_MEAN=[0.485,0.456,0.406]; IMAGENET_STD=[0.229,0.224,0.225]


def seed_everything(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)


def make_transforms():
    train_tf=transforms.Compose([
        transforms.Resize((256,256)), transforms.RandomResizedCrop(224,scale=(0.75,1.0)),
        transforms.RandomHorizontalFlip(), transforms.RandomVerticalFlip(p=0.10),
        transforms.RandomRotation(15), transforms.ColorJitter(brightness=0.15,contrast=0.15,saturation=0.10,hue=0.02),
        transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN,IMAGENET_STD)])
    eval_tf=transforms.Compose([transforms.Resize((224,224)),transforms.ToTensor(),transforms.Normalize(IMAGENET_MEAN,IMAGENET_STD)])
    return train_tf,eval_tf


def leaf_group(entry: str) -> str:
    stem=Path(entry).stem
    return stem.split("___",1)[0]


def grouped_split(entries, val_fraction=0.10, seed=42):
    groups={}
    for i,e in enumerate(entries): groups.setdefault(leaf_group(e),[]).append(i)
    keys=list(groups); random.Random(seed).shuffle(keys)
    target=max(1,int(len(entries)*val_fraction)); chosen=[]; total=0
    for key in keys:
        chosen.extend(groups[key]); total += len(groups[key])
        if total>=target: break
    val_set=set(chosen)
    train_idx=[i for i in range(len(entries)) if i not in val_set]
    return train_idx, sorted(val_set)


def class_weights(labels,num_classes):
    counts=np.bincount(labels,minlength=num_classes).astype(np.float64)
    weights=len(labels)/(num_classes*np.maximum(counts,1.0))
    return torch.tensor(weights,dtype=torch.float32)


def evaluate(model,loader,device):
    model.eval(); truth=[]; pred=[]; confidence=[]
    with torch.inference_mode():
        for x,y in loader:
            probs=torch.softmax(model(x.to(device)),dim=1); p=probs.argmax(1); c=probs.max(1).values
            truth += y.tolist(); pred += p.cpu().tolist(); confidence += c.cpu().tolist()
    return truth,pred,confidence


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True); p.add_argument("--train-manifest",required=True); p.add_argument("--test-manifest",required=True)
    p.add_argument("--epochs",type=int,default=15); p.add_argument("--batch-size",type=int,default=64); p.add_argument("--lr",type=float,default=3e-4)
    p.add_argument("--weight-decay",type=float,default=1e-4); p.add_argument("--patience",type=int,default=4); p.add_argument("--val-fraction",type=float,default=0.10)
    p.add_argument("--num-workers",type=int,default=2); p.add_argument("--output",default="ml/artifacts/best.pt"); p.add_argument("--seed",type=int,default=42); p.add_argument("--no-pretrained",action="store_true")
    args=p.parse_args(); seed_everything(args.seed)
    device=torch.device("cuda" if torch.cuda.is_available() else "cpu"); print(f"device={device}")
    if device.type=="cuda": print(f"gpu={torch.cuda.get_device_name(0)}")
    train_tf,eval_tf=make_transforms()
    base_train=PlantVillageManifestDataset(args.root,args.train_manifest,transform=train_tf)
    class_map=base_train.class_to_idx
    train_idx,val_idx=grouped_split(base_train.entries,args.val_fraction,args.seed)
    val_base=PlantVillageManifestDataset(args.root,args.train_manifest,transform=eval_tf,class_to_idx=class_map)
    test_ds=PlantVillageManifestDataset(args.root,args.test_manifest,transform=eval_tf,class_to_idx=class_map)
    train_ds=Subset(base_train,train_idx); val_ds=Subset(val_base,val_idx)
    labels=[class_map[base_train.labels[i]] for i in train_idx]
    weights=class_weights(labels,len(class_map)); print(f"classes={len(class_map)} train={len(train_ds)} val={len(val_ds)} test={len(test_ds)}")
    train_loader=DataLoader(train_ds,batch_size=args.batch_size,shuffle=True,num_workers=args.num_workers,pin_memory=device.type=="cuda",persistent_workers=args.num_workers>0)
    val_loader=DataLoader(val_ds,batch_size=args.batch_size,shuffle=False,num_workers=args.num_workers,pin_memory=device.type=="cuda",persistent_workers=args.num_workers>0)
    test_loader=DataLoader(test_ds,batch_size=args.batch_size,shuffle=False,num_workers=args.num_workers,pin_memory=device.type=="cuda",persistent_workers=args.num_workers>0)
    model=build_model(len(class_map),pretrained=not args.no_pretrained).to(device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=args.lr,weight_decay=args.weight_decay)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=max(args.epochs,1))
    criterion=nn.CrossEntropyLoss(weight=weights.to(device),label_smoothing=0.05)
    scaler=torch.amp.GradScaler("cuda",enabled=device.type=="cuda")
    best=-1.; stale=0; history=[]
    for epoch in range(args.epochs):
        model.train(); total_loss=0.; seen=0
        for x,y in train_loader:
            x=x.to(device,non_blocking=True); y=y.to(device,non_blocking=True); optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda",enabled=device.type=="cuda"): loss=criterion(model(x),y)
            scaler.scale(loss).backward(); scaler.step(optimizer); scaler.update(); total_loss+=loss.item()*len(y); seen+=len(y)
        scheduler.step(); truth,pred,conf=evaluate(model,val_loader,device)
        row={"epoch":epoch+1,"train_loss":total_loss/max(seen,1),"val_accuracy":accuracy_score(truth,pred),"val_macro_f1":f1_score(truth,pred,average="macro"),"val_weighted_f1":f1_score(truth,pred,average="weighted"),"mean_confidence":float(np.mean(conf))}; history.append(row)
        print(f"epoch={epoch+1}/{args.epochs} loss={row['train_loss']:.4f} val_accuracy={row['val_accuracy']:.4f} val_macro_f1={row['val_macro_f1']:.4f} val_weighted_f1={row['val_weighted_f1']:.4f}")
        if row["val_macro_f1"]>best:
            best=row["val_macro_f1"]; stale=0; save_checkpoint(model.cpu(),base_train.classes,args.output); model.to(device)
        else:
            stale+=1
            if stale>=args.patience: print(f"early_stopping epoch={epoch+1}"); break
    payload=torch.load(args.output,map_location=device,weights_only=False); model=build_model(len(payload["classes"]),pretrained=False).to(device); model.load_state_dict(payload["state_dict"])
    truth,pred,conf=evaluate(model,test_loader,device); labels_all=list(range(len(payload["classes"])))
    report=classification_report(truth,pred,labels=labels_all,target_names=payload["classes"],output_dict=True,zero_division=0)
    metrics={"dataset":"mohanty/PlantVillage","configuration":"color","train_images":len(base_train),"train_images_used":len(train_ds),"validation_images":len(val_ds),"test_images":len(test_ds),"classes":payload["classes"],"accuracy":accuracy_score(truth,pred),"macro_f1":f1_score(truth,pred,average="macro"),"weighted_f1":f1_score(truth,pred,average="weighted"),"mean_max_probability":float(np.mean(conf)),"low_confidence_rate_below_0.60":float(np.mean(np.asarray(conf)<0.60)),"confusion_matrix":confusion_matrix(truth,pred,labels=labels_all).tolist(),"classification_report":report,"history":history}
    out=Path(args.output); out.with_suffix(".metrics.json").write_text(json.dumps(metrics,indent=2),encoding="utf-8"); out.with_suffix(".classes.json").write_text(json.dumps({"class_to_idx":{c:i for i,c in enumerate(payload["classes"])},"classes":payload["classes"]},indent=2),encoding="utf-8")
    print("FINAL TEST"); print(f"accuracy={metrics['accuracy']:.4f}"); print(f"macro_f1={metrics['macro_f1']:.4f}"); print(f"weighted_f1={metrics['weighted_f1']:.4f}"); print(f"confidence<0.60={metrics['low_confidence_rate_below_0.60']:.4f}"); print(f"checkpoint={args.output}")

if __name__=="__main__": main()
