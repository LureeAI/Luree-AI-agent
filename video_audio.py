"""Original instrumental bed and optional paid AI narration; no third-party music files."""
import math
import os
import struct
import subprocess
import time
import wave
from pathlib import Path
import imageio_ffmpeg

RATE=24000
SECONDS=15

def make_music(path):
    # Soft original chord/arpeggio pattern, synthesized rather than copied from a track.
    chords=[(261.63,329.63,392.00),(220.00,261.63,329.63),
        (174.61,220.00,261.63),(196.00,246.94,293.66)]
    with wave.open(str(path),'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(RATE)
        buffer=bytearray()
        for sample in range(RATE*SECONDS):
            t=sample/RATE
            chord=chords[int(t/3.75)%4]
            step=int(t/0.375)
            beat=t%0.375
            frequency=chord[step%3]*2
            melody=math.sin(2*math.pi*frequency*t)*math.exp(-beat*10)*0.065
            pad=sum(math.sin(2*math.pi*f*t) for f in chord)*0.018
            bass=math.sin(2*math.pi*(chord[0]/2)*t)*0.025
            fade=min(t/0.4,1,(SECONDS-t)/0.8)
            value=max(-1,min(1,(melody+pad+bass)*max(0,fade)))
            buffer.extend(struct.pack('<h',int(value*32767)))
        output.writeframes(buffer)
    return Path(path)

def make_narration(script,path,language='en'):
    names={'ar':'Arabic','en':'English','ko':'Korean'}
    if language not in names:
        raise ValueError('Unsupported narration language')
    if not isinstance(script,str) or not script.strip() or len(script)>300:
        raise ValueError('Narration must be 1–300 characters')
    key=os.environ.get('OPENAI_API_KEY','').strip()
    if not key:
        raise RuntimeError('Narration needs OPENAI_API_KEY')
    from openai import OpenAI
    client=OpenAI(api_key=key,timeout=45,max_retries=0)
    deadline=time.monotonic()+60
    try:
        with client.audio.speech.with_streaming_response.create(
            model='gpt-4o-mini-tts',voice='nova',input=script,
            instructions=f'Speak only in {names[language]}. Read this short fashion advertisement clearly and warmly. Keep a natural, confident pace. Do not add words.',
            response_format='wav') as response:
            size=0
            with open(path,'wb') as output:
                for chunk in response.iter_bytes(chunk_size=65536):
                    size+=len(chunk)
                    if size>4*1024*1024 or time.monotonic()>deadline:
                        raise RuntimeError('Narration output exceeded limits')
                    output.write(chunk)
    finally:
        client.close()
    return Path(path)

def mux_audio(silent_video,music,narration,output):
    args=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(silent_video),'-i',str(music)]
    if narration:
        with wave.open(str(narration),'rb') as source:
            duration=source.getnframes()/source.getframerate()
        if duration<=0 or duration>22.5:
            raise ValueError('Narration is too long; shorten the script')
        pace=max(1,duration/14.0)
        args+=['-i',str(narration),'-filter_complex',
            f'[1:a]volume=0.65[m];[2:a]atempo={pace:.6f},adelay=250|250,apad[v];[m][v]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.9[a]']
    else:
        args+=['-filter_complex','[1:a]alimiter=limit=0.9[a]']
    args+=['-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac','-b:a','128k',
        '-t','15','-movflags','+faststart',str(output)]
    subprocess.run(args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
    return Path(output)

