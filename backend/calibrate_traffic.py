"""Interactive calibration for a stationary intersection clip only."""
import argparse, hashlib, json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixed-camera',action='store_true',required=True,help='Assert the entire clip uses a stationary camera')
    p.add_argument('--frame',type=int,default=0)
    args=p.parse_args()
    import cv2
    from edge.runtime import load_config
    cfg=load_config(); video=Path(cfg['traffic_video'])
    cap=cv2.VideoCapture(str(video));cap.set(cv2.CAP_PROP_POS_FRAMES,args.frame);ok,frame=cap.read();cap.release()
    if not ok: raise SystemExit('Could not read calibration frame')
    h,w=frame.shape[:2];scale=min(1,1200/w);preview=cv2.resize(frame,(int(w*scale),int(h*scale)))
    h,w=preview.shape[:2]
    print('Select ONLY the traffic light governing the lane being monitored, then Enter.')
    x,y,rw,rh=cv2.selectROI('Governing signal',preview,False);cv2.destroyAllWindows()
    if rw<=0 or rh<=0: raise SystemExit('Cancelled: no settings changed')
    points=[]
    def click(event,x,y,flags,param):
        if event==cv2.EVENT_LBUTTONDOWN and len(points)<3: points.append([x/w,y/h])
    title='Click stop-line endpoints, then point on APPROACH side; Enter saves; Esc cancels'
    cv2.namedWindow(title);cv2.setMouseCallback(title,click)
    while True:
        shown=preview.copy()
        for a,b in points: cv2.circle(shown,(int(a*w),int(b*h)),5,(0,255,255),-1)
        if len(points)>=2: cv2.line(shown,tuple(int(v*d) for v,d in zip(points[0],(w,h))),tuple(int(v*d) for v,d in zip(points[1],(w,h))),(0,0,255),2)
        cv2.imshow(title,shown);key=cv2.waitKey(30)&255
        if key==27: cv2.destroyAllWindows();raise SystemExit('Cancelled: no settings changed')
        if key in (10,13) and len(points)==3: break
    cv2.destroyAllWindows()
    a,b,q=points;cross=(b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0])
    if abs(cross)<.0001: raise SystemExit('Invalid line/approach point; no settings changed')
    path=Path(__file__).parent/'edge/enhancements.json';settings=json.loads(path.read_text())
    with video.open('rb') as handle: digest=hashlib.file_digest(handle,'sha256').hexdigest()
    settings['violations']={'enabled':True,'camera_mode':'fixed','video_sha256':digest,'stop_line':[a,b],
       'signal_roi':[x/w,y/h,(x+rw)/w,(y+rh)/h],'approach_side':1 if cross>0 else -1,'red_hold_seconds':.5}
    path.with_suffix('.json.bak').write_bytes(path.read_bytes())
    path.write_text(json.dumps(settings,indent=2))
    print('Calibration saved. Restart edge service. Alerts require stable RED and tracked crossing; review manually.')
if __name__=='__main__': main()
