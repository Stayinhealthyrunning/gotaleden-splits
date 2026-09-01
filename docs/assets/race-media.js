(function(){
  'use strict';
  const audioSource='assets/gotaleden-ultra.mp3?v=20260901-music1';
  const enabledStorageKey='gotaleden-music-enabled';
  const volumeStorageKey='gotaleden-music-volume';
  const defaultVolume=.35;
  const clamp=value=>Math.max(0,Math.min(1,Number(value)||0));
  function storedEnabled(){try{return localStorage.getItem(enabledStorageKey)!=='false'}catch{return true}}
  function storedVolume(){try{const stored=localStorage.getItem(volumeStorageKey);if(stored===null)return defaultVolume;const value=Number(stored);return Number.isFinite(value)&&value>=0?clamp(value):defaultVolume}catch{return defaultVolume}}
  const media={audioSource,enabledStorageKey,volumeStorageKey,defaultVolume,audioEnabled:storedEnabled(),volume:storedVolume(),setEnabled(value){this.audioEnabled=Boolean(value);try{localStorage.setItem(enabledStorageKey,String(this.audioEnabled))}catch{}return this.audioEnabled},setVolume(value){this.volume=clamp(value);try{localStorage.setItem(volumeStorageKey,String(this.volume))}catch{}return this.volume}};
  window.GotaledenMedia=media;
})();
