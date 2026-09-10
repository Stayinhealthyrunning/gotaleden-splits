(function(){
  'use strict';
  const clean=value=>typeof value==='string'?value.trim():'';
  const clamp=value=>Math.max(0,Math.min(1,Number(value)||0));
  const get=key=>{try{return localStorage.getItem(key)}catch{return null}};
  const set=(key,value)=>{try{localStorage.setItem(key,value)}catch{}};
  const firstStored=keys=>keys.map(get).find(value=>value!==null)??null;
  const media={
    audioSource:'',enabledStorageKey:'race-analysis:music-enabled',volumeStorageKey:'race-analysis:music-volume',defaultVolume:.35,audioEnabled:true,volume:.35,
    configure(event){
      const definition=event?.media||{},legacyEnabled=Array.isArray(definition.legacy_enabled_storage_keys)?definition.legacy_enabled_storage_keys:[],legacyVolume=Array.isArray(definition.legacy_volume_storage_keys)?definition.legacy_volume_storage_keys:[];
      this.audioSource=clean(definition.audio_source);this.enabledStorageKey=event?.storageKey?.('music-enabled')||'race-analysis:music-enabled';this.volumeStorageKey=event?.storageKey?.('music-volume')||'race-analysis:music-volume';this.defaultVolume=clamp(definition.default_volume??.35);
      const enabled=get(this.enabledStorageKey)??firstStored(legacyEnabled),volume=get(this.volumeStorageKey)??firstStored(legacyVolume);this.audioEnabled=enabled!=='false';this.volume=volume===null?this.defaultVolume:clamp(volume);
      if(get(this.enabledStorageKey)===null&&enabled!==null)set(this.enabledStorageKey,enabled);if(get(this.volumeStorageKey)===null&&volume!==null)set(this.volumeStorageKey,String(this.volume));return this;
    },
    setEnabled(value){this.audioEnabled=Boolean(value);set(this.enabledStorageKey,String(this.audioEnabled));return this.audioEnabled},
    setVolume(value){this.volume=clamp(value);set(this.volumeStorageKey,String(this.volume));return this.volume},
  };
  window.GRaceMedia=media;
})();
