"""Vertical photo-based dress videos; no generative-video service or external music."""
import io
import math
import time
from pathlib import Path
from urllib.parse import urlsplit
import warnings
import requests
from PIL import Image, ImageOps, ImageDraw, ImageFont
import imageio_ffmpeg

WIDTH, HEIGHT, FPS, SECONDS = 720, 1280, 24, 15
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_VIDEO_BYTES = 15 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 24_000_000

def download_photo(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != 'cdn.shopify.com' or parsed.port not in (None,443) or parsed.username or parsed.password:
        raise ValueError('Only Shopify CDN photos are allowed')
    deadline=time.monotonic()+30
    with requests.get(url,stream=True,timeout=(5,15),allow_redirects=False) as response:
        if response.status_code != 200:
            raise ValueError('Photo download failed')
        length=response.headers.get('Content-Length')
        if length and int(length)>MAX_IMAGE_BYTES:
            raise ValueError('Photo is too large')
        payload=bytearray()
        for chunk in response.iter_content(65536):
            if time.monotonic()>deadline:
                raise ValueError('Photo download timed out')
            payload.extend(chunk)
            if len(payload)>MAX_IMAGE_BYTES:
                raise ValueError('Photo is too large')
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(payload)) as photo:
            if photo.format not in ('JPEG','PNG','WEBP'):
                raise ValueError('Unsupported photo format')
            return ImageOps.exif_transpose(photo).convert('RGB').copy()

def font(size):
    # Pillow includes a scalable default Latin font: no host-specific font dependency.
    return ImageFont.load_default(size=size)

def wrapped(draw,text,width,size,lines):
    text=' '.join(text.split())
    words=text.split()
    result=[]
    current=''
    for word in words:
        candidate=(current+' '+word).strip()
        if draw.textlength(candidate,font=font(size))>width and current:
            result.append(current);current=word
        else:
            current=candidate
    if current:result.append(current)
    result=result[:lines]
    while result and draw.textlength(result[-1],font=font(size))>width:
        result[-1]=result[-1][:-1]
    return result

def compose(photo,progress,title,price,phase=None):
    frame=Image.new('RGB',(WIDTH,HEIGHT),'#10121a')
    # Keep the entire garment visible, with breathing room for the gentle zoom.
    base=ImageOps.contain(photo,(WIDTH-50,850))
    scale=1+0.025*progress
    zoom=base.resize((int(base.width*scale),int(base.height*scale)),Image.Resampling.LANCZOS)
    frame.paste(zoom,((WIDTH-zoom.width)//2,150+(850-zoom.height)//2))
    draw=ImageDraw.Draw(frame)
    draw.text((WIDTH//2,55),'Luree Fashions',font=font(40),fill='#eac884',anchor='mm')
    draw.line((60,104,WIDTH-60,104),fill='#9c814e',width=2)
    title=title if title.isascii() else 'Discover your next favorite dress'
    if phase is not None:
        if phase<0.2:
            title='Find your next favorite dress'
        elif phase>0.8:
            title='Discover it at Luree Fashions'
    for index,line in enumerate(wrapped(draw,title,WIDTH-70,29,2)):
        draw.text((WIDTH//2,1030+index*40),line,font=font(29),fill='#fffaf0',anchor='mm')
    if price:
        draw.text((WIDTH//2,1130),price,font=font(30),fill='#eac884',anchor='mm')
    draw.rounded_rectangle((230,1180,490,1245),radius=20,fill='#eac884')
    draw.text((WIDTH//2,1212),'Shop now',font=font(30),fill='#10121a',anchor='mm')
    return frame

def render_video(photos,title,price,path):
    if not 1<=len(photos)<=5:
        raise ValueError('Select one to five photos')
    path=Path(path)
    if path.suffix!='.mp4':
        raise ValueError('MP4 output required')
    writer=imageio_ffmpeg.write_frames(str(path),(WIDTH,HEIGHT),fps=FPS,
        codec='libx264',pix_fmt_in='rgb24',pix_fmt_out='yuv420p',
        quality=7,macro_block_size=16,ffmpeg_timeout=30,
        output_params=['-movflags','+faststart','-preset','veryfast','-threads','2'])
    deadline=time.monotonic()+180
    total=FPS*SECONDS
    try:
        writer.send(None)
        for index in range(total):
            if time.monotonic()>deadline:
                raise RuntimeError('Video rendering timed out')
            position=index/total*len(photos)
            scene=min(int(position),len(photos)-1)
            progress=position-scene
            frame=compose(photos[scene],progress,title,price,index/total)
            # Crossfade between real photos; no invented dress imagery.
            if progress>0.9 and scene<len(photos)-1:
                next_frame=compose(photos[scene+1],0,title,price,index/total)
                frame=Image.blend(frame,next_frame,(progress-0.9)/0.1)
            writer.send(frame.tobytes())
    finally:
        writer.close()
    if not path.exists() or not 0<path.stat().st_size<=MAX_VIDEO_BYTES:
        raise RuntimeError('Video output missing or too large')
    return path

