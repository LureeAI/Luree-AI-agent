import io
import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch,MagicMock
from video_audio import make_music,make_narration,mux_audio
import video_service

class AudioTests(unittest.TestCase):
    def test_music_is_original_15_second_pcm(self):
        with tempfile.TemporaryDirectory() as d:
            path=make_music(Path(d)/'music.wav')
            with wave.open(str(path),'rb') as source:
                self.assertEqual(source.getnframes()/source.getframerate(),15)
                self.assertEqual(source.getnchannels(),1)
                self.assertEqual(source.getsampwidth(),2)

    def test_narration_streams_with_no_automatic_paid_retries(self):
        client=MagicMock()
        client.audio.speech.with_streaming_response.create.return_value.__enter__.return_value.iter_bytes.return_value=[b'wave-data']
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}),patch('openai.OpenAI',return_value=client) as factory:
            output=make_narration('Discover your next favorite dress.',Path(d)/'voice.wav')
            self.assertEqual(output.read_bytes(),b'wave-data')
            self.assertEqual(factory.call_args.kwargs['max_retries'],0)
            self.assertEqual(client.audio.speech.with_streaming_response.create.call_args.kwargs['model'],'gpt-4o-mini-tts')
            client.close.assert_called_once()

    def test_three_language_instructions(self):
        for language,name in [('ar','Arabic'),('en','English'),('ko','Korean')]:
            client=MagicMock()
            client.audio.speech.with_streaming_response.create.return_value.__enter__.return_value.iter_bytes.return_value=[b'test']
            with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}),patch('openai.OpenAI',return_value=client):
                make_narration(video_service.DEFAULT_SCRIPTS[language],Path(d)/'voice.wav',language)
            self.assertIn(name,client.audio.speech.with_streaming_response.create.call_args.kwargs['instructions'])

    def test_narration_limits_checked_before_any_api_call(self):
        with patch('openai.OpenAI') as client:
            with self.assertRaises(ValueError):make_narration('x'*301,'/tmp/unused.wav')
            client.assert_not_called()
        with self.assertRaises(video_service.VideoError):
            video_service.create_video_job('product',['img'],True,True,'word '*41)

    def test_long_narration_refuses_cutting_words(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'voice.wav'
            with wave.open(str(path),'wb') as source:
                source.setnchannels(1);source.setsampwidth(2);source.setframerate(1000)
                source.writeframes(b'\0\0'*23000)
            with patch('video_audio.subprocess.run') as run:
                with self.assertRaises(ValueError):mux_audio('video.mp4','music.wav',path,Path(d)/'out.mp4')
                run.assert_not_called()

if __name__=='__main__':unittest.main()

