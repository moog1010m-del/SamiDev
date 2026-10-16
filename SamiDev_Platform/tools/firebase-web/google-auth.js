import {initializeApp, getApps} from 'firebase/app';
import {initializeAuth, inMemoryPersistence, browserPopupRedirectResolver, GoogleAuthProvider, signInWithPopup, signOut} from 'firebase/auth';
let auth;
export async function authenticateGoogle(config){
  if(!auth){
    const app=getApps().find(app=>app.name==='samidev-google')||initializeApp({apiKey:config.apiKey,projectId:config.projectId,authDomain:config.authDomain},'samidev-google');
    auth=initializeAuth(app,{persistence:inMemoryPersistence,popupRedirectResolver:browserPopupRedirectResolver});
  }
  const provider=new GoogleAuthProvider();provider.setCustomParameters({prompt:'select_account'});
  try{
    const result=await signInWithPopup(auth,provider);
    return {idToken:await result.user.getIdToken(),refreshToken:result.user.refreshToken};
  }finally{await signOut(auth);}
}
