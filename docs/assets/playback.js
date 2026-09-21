(function(){
  'use strict';
  const BASE_PLAYBACK_SECONDS=90;
  const AUDIO_FADE_SECONDS=5;
  const clamp=(value,min,max)=>Math.max(min,Math.min(max,Number(value)||0));
  const raceDelta=(maxTime,deltaMs,speed=1)=>Number(deltaMs)/1000*(Number(maxTime)/BASE_PLAYBACK_SECONDS)*Number(speed);
  const fadeVolume=(baseVolume,elapsedMs)=>clamp(baseVolume,0,1)*(1-clamp(Number(elapsedMs)/(AUDIO_FADE_SECONDS*1000),0,1));
  function createAudioController(audio,{getBaseVolume=()=>.35,isEnabled=()=>true,onError=()=>{},requestFrame=callback=>requestAnimationFrame(callback),cancelFrame=id=>cancelAnimationFrame(id),now=()=>performance.now()}={}){
    let fadeFrame=null,fadeStart=null,destroyed=false;
    const baseVolume=()=>clamp(getBaseVolume(),0,1);
    function cancelFade({restore=true}={}){if(fadeFrame!==null)cancelFrame(fadeFrame);fadeFrame=null;fadeStart=null;if(audio&&restore)audio.volume=baseVolume()}
    function play({restart=false}={}){cancelFade();if(!audio||destroyed||!isEnabled())return false;audio.loop=false;audio.playbackRate=1;if(restart)audio.currentTime=0;audio.volume=baseVolume();audio.play().catch(onError);return true}
    function pause(){cancelFade();audio?.pause()}
    function finish(startTime=now()){
      if(!audio||destroyed||!isEnabled()||audio.paused)return false;
      cancelFade();fadeStart=Number(startTime);
      const step=timestamp=>{if(destroyed||fadeStart===null)return;const elapsed=Number(timestamp)-fadeStart;audio.volume=fadeVolume(baseVolume(),elapsed);if(elapsed>=AUDIO_FADE_SECONDS*1000){audio.volume=0;audio.pause();fadeFrame=null;fadeStart=null;return}fadeFrame=requestFrame(step)};
      fadeFrame=requestFrame(step);return true
    }
    function reset(){cancelFade();if(!audio)return;audio.pause();audio.currentTime=0;audio.volume=baseVolume()}
    function setBaseVolume(){if(audio&&fadeFrame===null)audio.volume=baseVolume()}
    function disable(){cancelFade();audio?.pause()}
    function destroy(){destroyed=true;cancelFade({restore:false});if(audio){audio.pause();audio.currentTime=0}}
    return{play,pause,finish,reset,setBaseVolume,disable,destroy,get fading(){return fadeFrame!==null},get destroyed(){return destroyed}}
  }
  window.GRacePlayback={BASE_PLAYBACK_SECONDS,AUDIO_FADE_SECONDS,raceDelta,fadeVolume,createAudioController};
})();
