'use client'
import React, { useEffect, useState, useRef } from 'react'
import { getListing, getPriceHistory, getSimilar, fraudCheck } from '@/lib/api'
import ContactModal from '@/components/ContactModal'
import VinChecker from '@/components/VinChecker'
import ModelChecklist from '@/components/ModelChecklist'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'
const ELIGIBILITY_COLORS: Record<string, string> = { eligible:'#22C55E', needs_check:'#F97316', not_recommended:'#EF4444', oldtimer:'#A855F7' }
const AI_SCAN_MESSAGES = ['🧠 AI proverava detalje oglasa...','🧠 Provera Euro norme...','🧠 Analiza kilometraže...','🧠 Izračunavanje troška uvoza...']
const SOURCE_LABELS: Record<string, string> = { autoscout24:'AutoScout24', willhaben:'Willhaben', marktplaats:'Marktplaats', '2dehands':'2dehands', kleinanzeigen:'Kleinanzeigen', mobile_de:'Mobile.de' }

function countryBadge(c: string) {
  const f: Record<string,string> = {DE:'🇩🇪',AT:'🇦🇹',NL:'🇳🇱',BE:'🇧🇪',FR:'🇫🇷',IT:'🇮🇹',CH:'🇨🇭',ES:'🇪🇸',PL:'🇵🇱',DK:'🇩🇰',SE:'🇸🇪'}
  return f[c] ? `${f[c]} ${c}` : '✓ Verifikovan'
}

function getSerbiaEligibility(listing: any) {
  const year = listing.year ? Number(listing.year) : null
  const fuel = listing.fuel_type || null
  const age  = year ? (2026 - year) : null
  if (fuel==='electric') return {status:'eligible',emoji:'🟢',label:'Visoka verovatnoća uvoza',sublabel:'EV · 0% carine',reason:'Električna vozila oslobođena carine.',warnings:['Proveri tip punjača (Tip 2 / CCS).'],confidence:'high',carinaPct:0}
  if (age!==null&&age>=30) return {status:'oldtimer',emoji:'🟣',label:'Oldtimer — poseban režim',sublabel:'Starije od 30 god.',reason:'Poseban carinski tretman.',warnings:['Konsultuj carinskog agenta.'],confidence:'medium',carinaPct:5}
  if (!year) return {status:'needs_check',emoji:'🟠',label:'Proveriti detalje uvoza',sublabel:'Godište nepoznato',reason:'Bez potvrđenog godišta nije moguće proceniti Euro normu.',warnings:['Zatraži COC i datum prve registracije.'],confidence:'low',carinaPct:5}
  if (year>=2015) return {status:'eligible',emoji:'🟢',label:'Visoka verovatnoća uvoza',sublabel:`Euro 6 · ${year}.`,reason:'Euro 6 — bez ograničenja.',warnings:['Pribavi COC.',...(fuel==='diesel'?['Proveri DPF.']:[])],confidence:'high',carinaPct:5}
  if (year>=2011) return {status:'eligible',emoji:'🟢',label:'Verovatno uspešan uvoz',sublabel:`Euro 5 · ${year}.`,reason:'Euro 5 — može se uvesti.',warnings:['Pribavi COC.',...(fuel==='diesel'?['Dizel Euro 5 — proveri DPF.']:[])],confidence:'high',carinaPct:5}
  if (year>=2006) return {status:'eligible',emoji:fuel==='diesel'?'🟠':'🟢',label:fuel==='diesel'?'Proveriti Euro 4':'Verovatno uspešan uvoz',sublabel:`Euro 4 · ${year}.`,reason:'Euro 4 — minimalni uslov.',warnings:['Obavezno pribavi COC.',...(fuel==='diesel'?['Dizel Euro 4 — rizik DPF.']:[])],confidence:fuel==='diesel'?'medium':'high',carinaPct:5}
  if (year>=2001) return {status:'needs_check',emoji:'🟠',label:'Proveriti detalje uvoza',sublabel:`Euro 3 · ${year}.`,reason:'Euro 3 — komplikovano, ali moguće.',warnings:['Konsultuj carinskog agenta.'],confidence:'low',carinaPct:5}
  return {status:'not_recommended',emoji:'🔴',label:'Visok rizik pri uvozu',sublabel:`Prestara norma · ${year}.`,reason:'Ne ispunjava standarde za uvoz.',warnings:['Registracija u Srbiji verovatno nije moguća.'],confidence:'none',carinaPct:5}
}

function calcTrustScore(listing: any, vinResult?: any) {
  let score = 0
  const explanations: {text:string;ok:boolean}[] = []
  const year=listing.year?Number(listing.year):null, mileage=listing.mileage?Number(listing.mileage):null
  const delta=listing.price_delta_pct?Number(listing.price_delta_pct):null, imgCount=(listing.images||[]).length
  if (imgCount>=6){score+=10;explanations.push({text:`${imgCount} fotografija vozila`,ok:true})}
  else if (imgCount>=3){score+=6} else if (imgCount>=1){score+=2;explanations.push({text:'Malo fotografija vozila',ok:false})}
  else explanations.push({text:'Nema fotografija vozila',ok:false})
  if (year){score+=10;explanations.push({text:`Godište potvrđeno (${year})`,ok:true})} else explanations.push({text:'Godište nije navedeno',ok:false})
  if (mileage){const ann=year?mileage/(2026-year):null;if(ann&&ann>40000){score+=4;explanations.push({text:`Visoka godišnja km (~${Math.round(ann/1000)}k/god)`,ok:false})}else{score+=10;explanations.push({text:`Kilometraža deluje realno (${mileage.toLocaleString()} km)`,ok:true})}}else explanations.push({text:'Kilometraža nije navedena',ok:false})
  if (listing.fuel_type){score+=4;explanations.push({text:'Gorivo navedeno',ok:true})}else explanations.push({text:'Gorivo nije navedeno',ok:false})
  if (listing.transmission) score+=4
  if (delta!==null){if(delta<-25){score+=6;explanations.push({text:`Cena ${Math.abs(delta).toFixed(0)}% ispod proseka — proveri razlog`,ok:false})}else if(delta<-5){score+=20;explanations.push({text:`Cena ispod proseka za ${Math.abs(delta).toFixed(0)}%`,ok:true})}else if(delta<=10){score+=15;explanations.push({text:'Cena odgovara tržišnom proseku',ok:true})}else if(delta<=20){score+=8;explanations.push({text:`Cena iznad proseka za ${delta.toFixed(0)}%`,ok:false})}else{score+=3;explanations.push({text:`Cena znatno iznad proseka (${delta.toFixed(0)}%)`,ok:false})}}else if(listing.price) score+=8
  const descLen=(listing.description||'').length
  if(descLen>100){score+=8;explanations.push({text:'Detaljan opis vozila',ok:true})}else if(descLen>30){score+=4}else{explanations.push({text:'Kratak ili nedostaje opis',ok:false})}
  const elig=getSerbiaEligibility(listing)
  if(elig.confidence==='high'){score+=20;explanations.push({text:'Pogodan za uvoz u Srbiju',ok:true})}else if(elig.confidence==='medium'){score+=10}else if(elig.confidence==='low'){score+=4;explanations.push({text:'Nesigurnost pri uvozu',ok:false})}else{explanations.push({text:'Problematičan uvoz',ok:false})}
  if(vinResult){const hc=vinResult.mismatches?.some((m:any)=>m.severity==='critical'),hw=vinResult.mismatches?.some((m:any)=>m.severity==='warning');if(hc){score=Math.max(0,score-55);explanations.push({text:`🚨 VIN neslaganje: ${vinResult.mismatches.filter((m:any)=>m.severity==='critical').map((m:any)=>m.field).join(', ')}`,ok:false})}else if(hw){score=Math.max(0,score-25);explanations.push({text:'⚠️ VIN delimično neslaganje',ok:false})}else if(vinResult.match_status==='ok'){score=Math.min(100,score+15);explanations.push({text:'✅ VIN potvrđuje sve podatke',ok:true})}}else explanations.push({text:'VIN broj nije verifikovan',ok:false})
  score=Math.min(100,Math.max(0,Math.round(score)))
  const hcv=vinResult?.mismatches?.some((m:any)=>m.severity==='critical')
  let label='',color=''
  if(hcv){label='🚨 Kritično neslaganje podataka';color='#EF4444'}else if(score>=85){label='Veoma kvalitetan oglas';color='#22C55E'}else if(score>=70){label='Dobar oglas';color='#22C55E'}else if(score>=55){label='Delimično verifikovan';color='#F97316'}else{label='Oglas nije potpuno verifikovan';color='#EF4444'}
  const positives=explanations.filter(e=>e.ok).slice(0,3), negatives=explanations.filter(e=>!e.ok).slice(0,4)
  return {score,label,color,explanations,positives,negatives}
}

function calcImport(price: number, carinaPct: number) {
  const carina=Math.round(price*carinaPct/100), pdv=Math.round((price+carina)*0.20)
  return {carina,pdv,transport:420,reg:280,total:price+carina+pdv+420+280,carinaPct}
}

function calcFirstYear(price: number, year: number|null) {
  const age=year?2026-year:5
  const servis=age<=3?300:age<=7?600:1200, registracija=280, kvarovi=age<=3?200:age<=7?800:2000
  const total=servis+registracija+kvarovi, color=total<1500?'#22C55E':total<3000?'#EAB308':'#EF4444'
  return {servis,registracija,kvarovi,total,color}
}

function fmt(n: any){return Number(n).toLocaleString('de-DE')}
function fmtKm(km: any){const n=Number(km);if(!n||n<1||n>999999)return null;return n.toLocaleString('de-DE')+' km'}
function kWtoKS(kw: number){return Math.round(kw*1.3596)}
function fullImg(url: string){
  if(!url)return url
  if(url.includes('img.kleinanzeigen.de'))return url.replace(/rule=\$_\w+/,'rule=$_57.AUTO')
  if(url.includes('images.marktplaats.com'))return url.replace(/rule=ecg_mp_eps\$_\d+/,'rule=ecg_mp_eps$_57')
  return url.replace(/\/\d+x\d+\.(webp|jpg|jpeg|png)/i,'/800x600.$1')
}

function BottomSheet({open,onClose,title,children}:{open:boolean;onClose:()=>void;title:string;children:any}){
  if(!open)return null
  return(
    <div style={{position:'fixed',inset:0,zIndex:2000,display:'flex',flexDirection:'column',justifyContent:'flex-end'}}>
      <div onClick={onClose} style={{flex:1,background:'rgba(0,0,0,.55)',backdropFilter:'blur(4px)'}}/>
      <div style={{background:'var(--bg2)',borderRadius:'20px 20px 0 0',padding:'0 0 env(safe-area-inset-bottom,16px)',maxHeight:'85vh',overflow:'hidden',display:'flex',flexDirection:'column',boxShadow:'0 -8px 40px rgba(0,0,0,.4)'}}>
        <div style={{padding:'16px 20px 12px',borderBottom:'1px solid var(--border)',display:'flex',justifyContent:'space-between',alignItems:'center',flexShrink:0}}>
          <h3 style={{fontSize:16,fontWeight:700,margin:0}}>{title}</h3>
          <button onClick={onClose} style={{background:'none',border:'none',color:'var(--text3)',fontSize:20,cursor:'pointer'}}>✕</button>
        </div>
        <div style={{overflowY:'auto',padding:'16px 20px 20px'}}>{children}</div>
      </div>
    </div>
  )
}

function FullscreenGallery({images,startIndex,onClose}:{images:string[];startIndex:number;onClose:()=>void}){
  const [idx,setIdx]=useState(startIndex)
  const tx=useRef<number>(0)
  useEffect(()=>{setIdx(startIndex)},[startIndex])
  return(
    <div style={{position:'fixed',inset:0,zIndex:3000,background:'rgba(0,0,0,.97)',display:'flex',flexDirection:'column'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'14px 16px',flexShrink:0}}>
        <span style={{fontSize:14,color:'rgba(255,255,255,.7)',fontWeight:600}}>{idx+1} / {images.length}</span>
        <button onClick={onClose} style={{background:'rgba(255,255,255,.1)',border:'none',borderRadius:20,width:36,height:36,color:'#fff',fontSize:18,cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center'}}>✕</button>
      </div>
      <div onTouchStart={e=>{tx.current=e.changedTouches[0].clientX}} onTouchEnd={e=>{const d=tx.current-e.changedTouches[0].clientX;if(Math.abs(d)>50){if(d>0)setIdx(i=>Math.min(i+1,images.length-1));else setIdx(i=>Math.max(i-1,0))}}} style={{flex:1,display:'flex',alignItems:'center',justifyContent:'center',overflow:'hidden',touchAction:'pan-y',position:'relative'}}>
        <img src={fullImg(images[idx])} alt="" style={{maxWidth:'100%',maxHeight:'100%',objectFit:'contain',userSelect:'none',display:'block'}} onError={e=>{(e.target as HTMLImageElement).src=images[idx]}}/>
        {idx>0&&<button onClick={()=>setIdx(i=>i-1)} style={{position:'absolute',left:12,top:'50%',transform:'translateY(-50%)',background:'rgba(0,0,0,.6)',border:'1px solid rgba(255,255,255,.15)',borderRadius:'50%',width:44,height:44,color:'#fff',fontSize:22,cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center'}}>‹</button>}
        {idx<images.length-1&&<button onClick={()=>setIdx(i=>i+1)} style={{position:'absolute',right:12,top:'50%',transform:'translateY(-50%)',background:'rgba(0,0,0,.6)',border:'1px solid rgba(255,255,255,.15)',borderRadius:'50%',width:44,height:44,color:'#fff',fontSize:22,cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center'}}>›</button>}
      </div>
      {images.length>1&&<div style={{display:'flex',justifyContent:'center',gap:5,padding:'12px 0',flexShrink:0}}>{images.slice(0,12).map((_:string,i:number)=><div key={i} onClick={()=>setIdx(i)} style={{width:idx===i?20:6,height:6,borderRadius:3,background:idx===i?'#fff':'rgba(255,255,255,.3)',cursor:'pointer',transition:'all .2s'}}/>)}</div>}
    </div>
  )
}

function SwipeableImage({images,activeImg,setActiveImg,alt,trust,onScoreClick,enriched,onImageClick}:any){
  const tx=useRef<number>(0)
  const [hov,setHov]=useState(false)
  const sc=trust?(trust.score>=70?'#22C55E':trust.score>=40?'#F97316':'#EF4444'):'#9CA3AF'
  const vb=enriched?{text:'✓ Podaci provereni',color:'#22C55E'}:{text:'⚠ Delimično potvrđeno',color:'#F97316'}
  return(
    <div onTouchStart={e=>{tx.current=e.changedTouches[0].clientX}} onTouchEnd={e=>{const d=tx.current-e.changedTouches[0].clientX;if(Math.abs(d)>40){if(d>0)setActiveImg((i:number)=>Math.min(i+1,images.length-1));else setActiveImg((i:number)=>Math.max(i-1,0))}}} onMouseEnter={()=>setHov(true)} onMouseLeave={()=>setHov(false)}
      style={{position:'relative',width:'calc(100% + 32px)',marginLeft:-16,marginRight:-16,background:'#0d0d0d',overflow:'hidden',touchAction:'pan-y',borderRadius:'0 0 22px 22px'}}>
      {images[activeImg]?<img src={fullImg(images[activeImg])} alt={alt} onClick={onImageClick} style={{display:'block',width:'100%',height:'min(58vh,620px)',objectFit:'cover',objectPosition:'center 40%',userSelect:'none',cursor:'zoom-in',transition:'transform .3s',transform:hov?'scale(1.02)':'scale(1)'}} onError={e=>{(e.target as HTMLImageElement).src=images[activeImg]}}/>:<div style={{width:'100%',height:220,display:'flex',alignItems:'center',justifyContent:'center',fontSize:60}}>🚗</div>}
      <div style={{position:'absolute',top:12,left:12,display:'flex',flexDirection:'column',gap:7}}>
        <div style={{background:'rgba(0,0,0,.72)',backdropFilter:'blur(10px)',borderRadius:20,padding:'5px 11px',border:`1px solid ${vb.color}55`,display:'inline-flex',alignItems:'center',gap:5,alignSelf:'flex-start'}}>
          <span style={{fontSize:12}}>{enriched?'✅':'⚠️'}</span>
          <span style={{fontSize:12,fontWeight:700,color:'#fff'}}>{vb.text}</span>
        </div>
        {trust&&<div onClick={onScoreClick} style={{background:'rgba(0,0,0,.78)',backdropFilter:'blur(14px)',borderRadius:16,padding:'10px 14px',cursor:'pointer',border:`1px solid ${sc}66`,alignSelf:'flex-start',boxShadow:`0 4px 20px rgba(0,0,0,.4)`}}>
          <div style={{fontSize:9,color:'rgba(255,255,255,.45)',fontWeight:700,letterSpacing:'.09em',marginBottom:3}}>AI SCORE</div>
          <div style={{display:'flex',alignItems:'baseline',gap:3}}><span style={{fontSize:32,fontWeight:900,color:sc,lineHeight:1}}>{trust.score}</span><span style={{fontSize:13,color:'rgba(255,255,255,.35)'}}>/100</span></div>
          <div style={{fontSize:11,color:sc,fontWeight:700,marginTop:2}}>{trust.label}</div>
          <div style={{marginTop:6,display:'flex',flexDirection:'column',gap:2}}>
            {trust.positives.slice(0,2).map((p:any,i:number)=><div key={i} style={{fontSize:10,color:'rgba(34,197,94,.9)'}}>+ {p.text}</div>)}
            {trust.negatives.slice(0,2).map((n:any,i:number)=><div key={i} style={{fontSize:10,color:'rgba(249,115,22,.9)'}}>− {n.text}</div>)}
          </div>
        </div>}
      </div>
      {images.length>1&&<div style={{position:'absolute',top:10,right:10,background:'rgba(0,0,0,.72)',backdropFilter:'blur(6px)',borderRadius:20,padding:'5px 12px',border:'1px solid rgba(255,255,255,.15)'}}><span style={{fontSize:13,fontWeight:600,color:'#fff'}}>{activeImg+1} / {images.length}</span></div>}
      {images.length>1&&<div style={{position:'absolute',bottom:10,left:'50%',transform:'translateX(-50%)',display:'flex',gap:6,alignItems:'center'}}>{images.slice(0,8).map((_:string,i:number)=><div key={i} onClick={()=>setActiveImg(i)} style={{width:activeImg===i?22:7,height:7,borderRadius:4,background:activeImg===i?'var(--accent)':'rgba(255,255,255,.35)',cursor:'pointer',transition:'all .25s'}}/>)}</div>}
      {images.length>1&&activeImg>0&&<div onClick={e=>{e.stopPropagation();setActiveImg(activeImg-1)}}
      {images.length>1&&activeImg<images.length-1&&<div onClick={e=>{e.stopPropagation();setActiveImg((i:number)=>i+1)}} style={{position:'absolute',right:8,top:'50%',transform:'translateY(-50%)',background:'rgba(0,0,0,.5)',borderRadius:'50%',width:36,height:36,display:'flex',alignItems:'center',justifyContent:'center',cursor:'pointer',color:'#fff',fontSize:18}}>›</div>}
    </div>
  )
}

function SideSection({title,children,accent}:{title:string;children:any;accent?:string}){
  return(
    <div style={{background:'var(--bg2)',border:`1px solid ${accent?accent+'33':'var(--border)'}`,borderRadius:14,padding:16,marginBottom:12}}>
      <div style={{fontSize:10,color:accent||'var(--text3)',fontWeight:700,letterSpacing:'.08em',marginBottom:12,textTransform:'uppercase'}}>{title}</div>
      {children}
    </div>
  )
}

export default function ListingPage({params}:{params:{id:string}}){
  const [listing,setListing]=useState<any>(null)
  const [similar,setSimilar]=useState<any[]>([])
  const [fraud,setFraud]=useState<any>(null)
  const [activeImg,setActiveImg]=useState(0)
  const [favorited,setFavorited]=useState(false)
  const [vinResult,setVinResult]=useState<any>(null)
  const [loading,setLoading]=useState(true)
  const [showContact,setShowContact]=useState(false)
  const [showBd,setShowBd]=useState(false)
  const [enriching,setEnriching]=useState(false)
  const [enriched,setEnriched]=useState(false)
  const [scanMsg,setScanMsg]=useState(AI_SCAN_MESSAGES[0])
  const [backUrl,setBackUrl]=useState('/search')
  const [showScoreSheet,setShowScoreSheet]=useState(false)
  const [showBdSheet,setShowBdSheet]=useState(false)
  const [showGallery,setShowGallery]=useState(false)
  const scanInterval=useRef<any>(null)

  useEffect(()=>{const p=sessionStorage.getItem('autoai_search_url');if(p)setBackUrl(p)},[])
  useEffect(()=>{
    Promise.allSettled([getListing(params.id),getSimilar(params.id),fraudCheck(params.id)])
      .then(([l,s,f])=>{
        if(l.status==='fulfilled'){const d=l.value;setListing(d);if(d?.url&&(!d.year||!d.mileage))autoEnrich(d.url)}
        if(s.status==='fulfilled')setSimilar(s.value)
        if(f.status==='fulfilled')setFraud(f.value)
      }).finally(()=>setLoading(false))
  },[params.id])

  const startScan=()=>{let i=0;setScanMsg(AI_SCAN_MESSAGES[0]);scanInterval.current=setInterval(()=>{i=(i+1)%AI_SCAN_MESSAGES.length;setScanMsg(AI_SCAN_MESSAGES[i])},1800)}
  const stopScan=()=>{if(scanInterval.current)clearInterval(scanInterval.current)}

  const autoEnrich=async(url:string)=>{
    if(enriching||enriched)return
    setEnriching(true);startScan()
    try{
      const res=await fetch(`${API_BASE}/analyze/`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})})
      const data=await res.json()
      if(data.scrape_success){setListing((prev:any)=>({...prev,year:data.year||prev.year,mileage:data.mileage||prev.mileage,fuel_type:data.fuel_type||prev.fuel_type,engine_power_kw:data.engine_power_kw||prev.engine_power_kw,country:data.country||prev.country,city:data.city||prev.city,transmission:data.transmission||prev.transmission,images:(data.images?.length||0)>(prev.images?.length||0)?data.images:prev.images}));setEnriched(true)}
    }catch{}
    stopScan();setEnriching(false)
  }

  if(loading)return <PageSkeleton/>
  if(!listing)return <div style={{textAlign:'center',padding:'80px 0',color:'var(--text3)'}}>Oglas nije pronađen.</div>

  const images=listing.images||[]
  const elig=getSerbiaEligibility(listing)
  const eligColor=ELIGIBILITY_COLORS[elig.status]||'#F97316'
  const price=listing.price?Number(listing.price):null
  const bd=price?calcImport(price,elig.carinaPct):null
  const deltaGood=listing.price_delta_pct&&Number(listing.price_delta_pct)<0
  const trust=calcTrustScore(listing,vinResult)
  const firstYear=price?calcFirstYear(price,listing.year):null
  const portalName=SOURCE_LABELS[listing.source]||listing.source||'Portal'
  const kw=listing.engine_power_kw?Number(listing.engine_power_kw):null
  const ks=kw?kWtoKS(kw):null
  const fuelLabel=(f:string)=>({diesel:'Dizel',petrol:'Benzin',gasoline:'Benzin',benzin:'Benzin',electric:'Električni',elektrisch:'Električni',hybrid:'Hibrid',lpg:'Plin',cng:'CNG'} as any)[f?.toLowerCase()]||f

  const specs=[
    {label:'Godište',value:listing.year},
    {label:'Km',value:fmtKm(listing.mileage)},
    {label:'Gorivo',value:listing.fuel_type?fuelLabel(listing.fuel_type):null},
    {label:'Menjač',value:listing.transmission==='automatic'?'Automatik':listing.transmission==='manual'?'Manuel':listing.transmission},
    {label:'Snaga',value:kw?`${kw} kW / ${ks} KS`:null},
    {label:'Karoserija',value:listing.body_type},
    {label:'Emisija',value:listing.euro_norm||null},
    {label:'Pogon',value:listing.drive_type||null},
    {label:'Zapremina',value:listing.engine_displacement?`${listing.engine_displacement} cm³`:null},
    {label:'Vlasnici',value:listing.num_owners?`${listing.num_owners}`:null},
    {label:'Zemlja',value:listing.country},
    {label:'Grad',value:listing.city?listing.city.split(' - ')[0]:null},
  ].filter(s=>s.value)

  const handleSave=async()=>{
    const t=localStorage.getItem('autoai_token');if(!t){window.location.href='/login';return}
    try{const r=await fetch(`${API_BASE}/users/me/favorites`,{method:'POST',headers:{'Content-Type':'application/json','Authorization':`Bearer ${t}`},body:JSON.stringify({listing_id:listing.id})});if(r.ok)setFavorited(true)}catch{}
  }

  return(
    <div style={{paddingBottom:0}}>
      {showContact&&<ContactModal listing={listing} onClose={()=>setShowContact(false)}/>}
      {showGallery&&images.length>0&&<FullscreenGallery images={images} startIndex={activeImg} onClose={()=>setShowGallery(false)}/>}

      <BottomSheet open={showScoreSheet} onClose={()=>setShowScoreSheet(false)} title={`AI Score: ${trust.score}/100`}>
        <div style={{marginBottom:16}}>
          <div style={{height:8,background:'rgba(255,255,255,.06)',borderRadius:4,overflow:'hidden',marginBottom:8}}><div style={{height:'100%',borderRadius:4,width:`${trust.score}%`,background:trust.color,transition:'width .6s'}}/></div>
          <div style={{fontSize:15,fontWeight:700,color:trust.color}}>{trust.label}</div>
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:6,marginBottom:16}}>
          {trust.positives.length>0&&<div><div style={{fontSize:11,color:'var(--text3)',fontWeight:600,marginBottom:6}}>POZITIVNO</div>{trust.positives.map((e:any,i:number)=><div key={i} style={{display:'flex',alignItems:'flex-start',gap:8,padding:'7px 10px',background:'rgba(34,197,94,.07)',borderRadius:8,marginBottom:4}}><span>✅</span><span style={{fontSize:13,color:'var(--text2)'}}>{e.text}</span></div>)}</div>}
          {trust.negatives.length>0&&<div><div style={{fontSize:11,color:'var(--text3)',fontWeight:600,marginBottom:6}}>NA ČEMU TREBA RADITI</div>{trust.negatives.map((e:any,i:number)=><div key={i} style={{display:'flex',alignItems:'flex-start',gap:8,padding:'7px 10px',background:'rgba(249,115,22,.07)',borderRadius:8,marginBottom:4}}><span>⚠️</span><span style={{fontSize:13,color:'var(--text2)'}}>{e.text}</span></div>)}</div>}
        </div>
        <p style={{fontSize:11,color:'var(--text3)',lineHeight:1.6,opacity:.7}}>Score se poboljšava sa VIN verifikacijom i kompletnim podacima oglasa.</p>
      </BottomSheet>

      <BottomSheet open={showBdSheet} onClose={()=>setShowBdSheet(false)} title="🇷🇸 Trošak uvoza u Srbiju">
        {bd&&<div>
          <div style={{fontSize:28,fontWeight:800,color:'var(--accent)',marginBottom:16}}>{fmt(bd.total)} €</div>
          {[{label:'EU cena',val:price!,note:''},{label:`Carina (${bd.carinaPct}%)`,val:bd.carina,note:bd.carinaPct===0?'oslobođeno':'srbija'},{label:'PDV (20%)',val:bd.pdv,note:'srbija'},{label:'Transport EU→RS',val:bd.transport,note:'procena'},{label:'Registracija',val:bd.reg,note:'procena'}].map(({label,val,note},i)=>(
            <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'11px 0',borderBottom:'1px solid var(--border)'}}>
              <span style={{fontSize:14,color:i===0?'var(--text)':'var(--text2)'}}>{i>0&&'+ '}{label}{note&&<span style={{fontSize:11,marginLeft:5,opacity:.6}}>({note})</span>}</span>
              <span style={{fontSize:14,fontWeight:600,color:i===0?'var(--text)':'var(--accent)'}}>{fmt(val)} €</span>
            </div>
          ))}
          <div style={{display:'flex',justifyContent:'space-between',marginTop:14,paddingTop:14,borderTop:'2px solid rgba(255,107,0,.25)'}}><span style={{fontSize:16,fontWeight:700}}>Ukupno za Srbiju</span><span style={{fontSize:18,fontWeight:800,color:'var(--accent)'}}>{fmt(bd.total)} €</span></div>
          <p style={{fontSize:11,color:'var(--text3)',marginTop:10,lineHeight:1.5,opacity:.7}}>* Procena je informativna. Provjeri sa carinskim agentom.</p>
        </div>}
      </BottomSheet>

      <style>{`
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
        @media(max-width:768px){.listing-grid{grid-template-columns:1fr!important}.desktop-sidebar{display:none!important}.desktop-section{display:none!important}.mobile-stack{display:block!important}}
        @media(min-width:769px){.mobile-stack{display:none!important}}
        .mobile-stack{display:block}.trust-bar{transition:width .6s ease}.sdbtn{transition:all .15s}.sdbtn:hover{opacity:.85;transform:translateY(-1px)}
      `}</style>

      <div className="container" style={{padding:'0 0 0'}}>
        <div style={{fontSize:14,color:'var(--text3)',marginBottom:10,display:'flex',alignItems:'center',gap:6,padding:'12px 16px 0'}}>
          <a href={backUrl} style={{color:'var(--text3)',textDecoration:'none'}}>← Pretraga</a>
          <span style={{opacity:.4}}>·</span>
          <span style={{color:'var(--text)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{listing.make} {listing.model}</span>
        </div>

        {enriching&&<div style={{background:'rgba(99,102,241,.08)',border:'1px solid rgba(99,102,241,.25)',borderRadius:10,padding:'9px 14px',margin:'0 16px 10px',display:'flex',alignItems:'center',gap:8}}><div style={{width:7,height:7,borderRadius:'50%',background:'#818CF8',animation:'pulse 1s infinite',flexShrink:0}}/><span style={{fontSize:12,color:'#818CF8',fontWeight:600}}>{scanMsg}</span></div>}

        {vinResult?.mismatches?.some((m:any)=>m.severity==='critical')&&(
          <div style={{background:'rgba(239,68,68,.08)',border:'2px solid rgba(239,68,68,.5)',borderRadius:14,padding:'14px 16px',margin:'0 16px 12px'}}>
            <div style={{fontSize:16,fontWeight:800,color:'#EF4444',marginBottom:10}}>🚨 VIN SE NE POKLAPA SA OGLASOM</div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:10}}>
              <div style={{background:'rgba(239,68,68,.08)',borderRadius:10,padding:'10px 12px'}}><div style={{fontSize:10,color:'#EF4444',fontWeight:700,marginBottom:6}}>📋 VIN PODACI</div>{[{label:'Marka',value:vinResult.make},{label:'Model',value:vinResult.model},{label:'Godište',value:vinResult.year}].filter(f=>f.value).map(({label,value})=><div key={label} style={{fontSize:12,marginBottom:3}}><span style={{color:'var(--text3)'}}>{label}: </span><span style={{color:'#EF4444',fontWeight:700}}>{String(value)}</span></div>)}</div>
              <div style={{background:'rgba(255,255,255,.04)',borderRadius:10,padding:'10px 12px'}}><div style={{fontSize:10,color:'var(--text3)',fontWeight:700,marginBottom:6}}>📝 OGLAS NAVODI</div>{[{label:'Marka',value:listing.make},{label:'Model',value:listing.model},{label:'Godište',value:listing.year}].filter(f=>f.value).map(({label,value})=><div key={label} style={{fontSize:12,marginBottom:3}}><span style={{color:'var(--text3)'}}>{label}: </span><span style={{fontWeight:600}}>{String(value)}</span></div>)}</div>
            </div>
            <div style={{background:'rgba(239,68,68,.06)',borderRadius:8,padding:'10px 12px',fontSize:12,color:'var(--text2)',lineHeight:1.6}}>⛔ <strong style={{color:'#EF4444'}}>Ne preporučujemo kupovinu</strong> dok prodavac ne objasni neslaganje podataka.</div>
          </div>
        )}

        <div className="listing-grid" style={{display:'grid',gridTemplateColumns:'1fr 340px',gap:24,alignItems:'start'}}>

          {/* MOBILE */}
          <div className="mobile-stack">
            <SwipeableImage images={images} activeImg={activeImg} setActiveImg={setActiveImg} alt={`${listing.make} ${listing.model}`} trust={trust} onScoreClick={()=>setShowScoreSheet(true)} enriched={enriched} onImageClick={()=>setShowGallery(true)}/>

            <div style={{padding:'16px 16px 0'}}>
              <div style={{fontSize:28,fontWeight:800,fontFamily:'Syne,sans-serif',marginBottom:6,lineHeight:1.2}}>{listing.make} {listing.model}</div>
              <div style={{display:'flex',gap:6,flexWrap:'wrap',fontSize:12,color:'var(--text3)',marginBottom:14,alignItems:'center'}}>
                {listing.year&&<span>{listing.year}</span>}
                {listing.mileage&&<><span style={{opacity:.3}}>·</span><span>{fmtKm(listing.mileage)}</span></>}
                {listing.fuel_type&&<><span style={{opacity:.3}}>·</span><span>{fuelLabel(listing.fuel_type)}</span></>}
                {listing.transmission&&<><span style={{opacity:.3}}>·</span><span>{listing.transmission==='automatic'?'Automatik':'Manuel'}</span></>}
                {ks&&<><span style={{opacity:.3}}>·</span><span>{ks} KS</span></>}
                {listing.city&&<><span style={{opacity:.3}}>·</span><span>{listing.city.split(' - ')[0]}</span></>}
              </div>
            </div>

            <div style={{padding:'0 16px 16px'}}>
              <div style={{fontSize:44,fontWeight:800,color:'var(--text)',lineHeight:1,letterSpacing:'-1px'}}>{price?`${fmt(price)} €`:'Na upit'}</div>
              {listing.price_delta_pct&&<div style={{fontSize:13,marginTop:6,display:'flex',alignItems:'center',gap:6}}><span style={{color:'var(--text3)'}}>AI procena:</span><span style={{fontWeight:700,color:deltaGood?'#22C55E':'#F97316'}}>{deltaGood?'Ispod tržišta':Math.abs(Number(listing.price_delta_pct))<=10?'Fer cena':'Iznad tržišta'} {deltaGood?'↓':'↑'}{Math.abs(Number(listing.price_delta_pct)).toFixed(0)}%</span></div>}
              {listing.price_estimated&&<div style={{fontSize:12,color:'var(--text3)',marginTop:3}}>Tržišna vrednost: <span style={{color:'var(--text2)',fontWeight:600}}>{fmt(listing.price_estimated)} €</span> <span style={{opacity:.6,cursor:'help'}} title="Izračunato iz sličnih oglasa, kilometraže, godišta i opreme.">ⓘ</span></div>}
            </div>

            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,padding:'0 16px 16px'}}>
              <div style={{background:`${eligColor}0d`,border:`1px solid ${eligColor}33`,borderRadius:14,padding:'14px',minHeight:90}}>
                <div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.06em',marginBottom:6}}>UVOZ U SRBIJU</div>
                <div style={{fontSize:17,fontWeight:800,color:eligColor,marginBottom:4,lineHeight:1.2}}>{elig.emoji} {elig.label}</div>
                {elig.sublabel&&<div style={{fontSize:11,color:'var(--text3)',lineHeight:1.4}}>{elig.sublabel}</div>}
              </div>
              {bd?<button onClick={()=>setShowBdSheet(true)} style={{background:'rgba(255,107,0,.07)',border:'1px solid rgba(255,107,0,.25)',borderRadius:14,padding:'14px',textAlign:'left',cursor:'pointer',width:'100%',minHeight:90}}>
                <div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.06em',marginBottom:6}}>ZA SRBIJU</div>
                <div style={{fontSize:22,fontWeight:900,color:'var(--accent)',lineHeight:1,marginBottom:4}}>{fmt(bd.total)} €</div>
                <div style={{fontSize:11,color:'var(--text3)'}}>Detalji →</div>
              </button>:<div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:14,padding:'14px',minHeight:90}}><div style={{fontSize:13,color:'var(--text3)'}}>Nedostaje cena</div></div>}
            </div>

            <div style={{display:'grid',gridTemplateColumns:'2fr 1fr 1fr',gap:10,padding:'0 16px 20px'}}>
              <button onClick={()=>setShowContact(true)} style={{height:64,background:'var(--accent)',border:'none',color:'#fff',borderRadius:16,fontSize:15,fontWeight:800,cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',gap:8,boxShadow:'0 4px 20px rgba(255,107,0,.35)'}}>🤖 Kontaktiraj</button>
              <button onClick={handleSave} style={{height:52,background:favorited?'rgba(255,107,0,.12)':'var(--bg2)',border:`2px solid ${favorited?'var(--accent)':'var(--border)'}`,color:favorited?'var(--accent)':'var(--text2)',borderRadius:14,fontSize:12,fontWeight:700,cursor:'pointer',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:2}}>
                <span style={{fontSize:17}}>{favorited?'❤️':'🤍'}</span><span style={{fontSize:10}}>{favorited?'Sačuvano':'Sačuvaj'}</span>
              </button>
              <button onClick={()=>images.length>0&&setShowGallery(true)} style={{height:52,background:'var(--bg2)',border:'2px solid var(--border)',color:'var(--text2)',borderRadius:14,fontSize:12,fontWeight:700,cursor:'pointer',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:2}}>
                <span style={{fontSize:17}}>🖼️</span><span style={{fontSize:10}}>{images.length} sl.</span>
              </button>
            </div>

            {listing.url&&<div style={{padding:'0 16px 16px'}}><a href={listing.url} target="_blank" rel="noopener" style={{display:'flex',alignItems:'center',justifyContent:'center',gap:8,width:'100%',padding:'13px',borderRadius:12,background:'var(--bg2)',border:'1px solid var(--border)',color:'var(--text2)',fontSize:13,fontWeight:600,textDecoration:'none'}}>🔗 Pogledaj na {portalName} →</a></div>}

            <div style={{paddingLeft:16,paddingRight:16}}>
              <MobileTabs listing={listing} elig={elig} eligColor={eligColor} bd={bd} trust={trust} specs={specs} similar={similar} price={price} deltaGood={deltaGood} onContact={()=>setShowContact(true)} onShowScore={()=>setShowScoreSheet(true)} onShowBd={()=>setShowBdSheet(true)} enriching={enriching} enriched={enriched} scanMsg={scanMsg} onEnrich={()=>autoEnrich(listing.url)} fraud={fraud} onVinResult={setVinResult} vinResult={vinResult} kw={kw} ks={ks} portalName={portalName} saved={favorited} onSave={handleSave} firstYear={firstYear} fuelLabel={fuelLabel} images={images} onGallery={()=>setShowGallery(true)}/>
            </div>
          </div>

          {/* DESKTOP LEVA */}
          <div className="desktop-section" style={{display:'block'}}>
            <div style={{borderRadius:14,overflow:'hidden',marginBottom:8,position:'relative',background:'#0b0b12',userSelect:'none'}}>
              {images[activeImg]
                ?<img src={fullImg(images[activeImg])} alt={`${listing.make} ${listing.model}`}
                    onClick={()=>setShowGallery(true)}
                    style={{width:'100%',maxHeight:'75vh',minHeight:320,objectFit:'contain',display:'block',cursor:'zoom-in',transition:'opacity .2s ease,transform .2s ease'}}
                    onError={e=>{(e.target as HTMLImageElement).src=images[activeImg]}}/>
                :<div style={{display:'flex',alignItems:'center',justifyContent:'center',height:400,fontSize:60}}>🚗</div>
              }
              <div style={{position:'absolute',bottom:8,left:8,background:'rgba(0,0,0,.75)',borderRadius:6,padding:'3px 9px',fontSize:11,color:'rgba(255,255,255,.85)'}}>{countryBadge(listing.country||'')}</div>
              {images.length>1&&<>
                <button onClick={e=>{e.stopPropagation();setActiveImg(i=>Math.max(i-1,0))}} style={{position:'absolute',left:10,top:'50%',transform:'translateY(-50%)',background:'rgba(0,0,0,.55)',border:'1px solid rgba(255,255,255,.18)',borderRadius:'50%',width:42,height:42,color:'#fff',fontSize:20,cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',backdropFilter:'blur(6px)',transition:'all .15s'}}>‹</button>
                <button onClick={e=>{e.stopPropagation();setActiveImg(i=>Math.min(i+1,images.length-1))}} style={{position:'absolute',right:10,top:'50%',transform:'translateY(-50%)',background:'rgba(0,0,0,.55)',border:'1px solid rgba(255,255,255,.18)',borderRadius:'50%',width:42,height:42,color:'#fff',fontSize:20,cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',backdropFilter:'blur(6px)',transition:'all .15s'}}>›</button>
                <div onClick={()=>setShowGallery(true)} style={{position:'absolute',top:10,right:10,background:'rgba(0,0,0,.7)',borderRadius:20,padding:'5px 12px',fontSize:12,color:'#fff',fontWeight:600,cursor:'pointer',backdropFilter:'blur(6px)',border:'1px solid rgba(255,255,255,.12)'}}>{activeImg+1} / {images.length}</div>
              </>}
            </div>
            {images.length>1&&(
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:16,padding:'0 2px'}}>
                <span style={{fontSize:12,color:'var(--text3)'}}>{images.length} fotografija vozila</span>
                <button onClick={()=>setShowGallery(true)} style={{background:'rgba(255,255,255,.05)',border:'1px solid var(--border)',borderRadius:8,padding:'5px 14px',fontSize:12,color:'var(--text2)',cursor:'pointer'}}>🖼 Prikaži sve slike →</button>
              </div>
            )}

            <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:14,padding:16,marginBottom:12}}>
              <div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.08em',marginBottom:12}}>SPECIFIKACIJE</div>
              <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:8}}>
                {specs.map((s:any)=>(
                  <div key={s.label} style={{background:'var(--bg3)',borderRadius:10,padding:'10px 12px'}}>
                    <div style={{fontSize:10,color:'var(--text3)',marginBottom:3,letterSpacing:'.04em'}}>{s.label.toUpperCase()}</div>
                    <div style={{fontSize:13,fontWeight:700,color:'var(--text)',lineHeight:1.3}}>
                      {s.label==='Grad'?<a href={`https://maps.google.com/?q=${encodeURIComponent([listing.city,listing.country].filter(Boolean).join(', '))}`} target="_blank" rel="noopener" style={{color:'inherit',textDecoration:'none'}}>{s.value} 📍</a>:s.value}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {listing.make&&<div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:14,padding:16,marginBottom:12}}>
              <div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.08em',marginBottom:12}}>ŠTA PROVERITI</div>
              <ModelChecklist make={listing.make} model={listing.model} year={listing.year} fuelType={listing.fuel_type} transmission={listing.transmission}/>
            </div>}

            {firstYear&&<div style={{background:'var(--bg2)',border:`1px solid ${firstYear.color}33`,borderRadius:14,padding:16,marginBottom:12}}>
              <div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.08em',marginBottom:12}}>PROCENA TROŠKOVA PRVE GODINE</div>
              {[{label:'Redovan servis',val:firstYear.servis,c:'#22C55E'},{label:'Registracija',val:firstYear.registracija,c:'#22C55E'},{label:'Neočekivani kvarovi',val:firstYear.kvarovi,c:'#EF4444'}].map(({label,val,c},i)=>(
                <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'6px 0',borderBottom:'1px solid var(--border)'}}><span style={{fontSize:13,color:'var(--text2)'}}>{label}</span><span style={{fontSize:13,fontWeight:600,color:c}}>{fmt(val)} €</span></div>
              ))}
              <div style={{display:'flex',justifyContent:'space-between',marginTop:10,paddingTop:8,borderTop:`2px solid ${firstYear.color}44`}}><span style={{fontSize:14,fontWeight:700}}>Ukupno</span><span style={{fontSize:15,fontWeight:800,color:firstYear.color}}>{fmt(firstYear.total)} €</span></div>
              <div style={{fontSize:11,color:'var(--text3)',marginTop:8,opacity:.7}}>* Procena zasnovana na starosti i marki vozila.</div>
            </div>}

            <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:14,padding:16,marginBottom:12}}>
              <div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.08em',marginBottom:8}}>VIN PROVERA VOZILA</div>
              <p style={{fontSize:12,color:'var(--text3)',margin:'0 0 12px',lineHeight:1.5}}>Zatraži VIN od prodavca koristeći{' '}<button onClick={()=>setShowContact(true)} style={{background:'none',border:'none',color:'var(--accent)',cursor:'pointer',fontSize:12,fontWeight:600,padding:0,textDecoration:'underline'}}>Kontaktiraj prodavca</button>{' '}— AI automatski dodaje pitanje na jeziku prodavca.</p>
              <VinChecker listing={listing} onVinResult={setVinResult}/>
            </div>

            {listing.description&&<div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:14,padding:16,marginBottom:12}}><div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.08em',marginBottom:10}}>OPIS</div><p style={{color:'var(--text2)',lineHeight:1.8,fontSize:13,whiteSpace:'pre-line',margin:0}}>{listing.description}</p></div>}
            {listing.features?.length>0&&<div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:14,padding:16,marginBottom:12}}><div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.08em',marginBottom:10}}>OPREMA ({listing.features.length})</div><div style={{display:'flex',flexWrap:'wrap',gap:5}}>{listing.features.map((f:string)=><span key={f} style={{background:'var(--bg3)',border:'1px solid var(--border)',borderRadius:20,padding:'3px 10px',fontSize:11,color:'var(--text2)'}}>{f}</span>)}</div></div>}
            {similar.length>0&&<div><div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.08em',marginBottom:12}}>SLIČNI OGLASI</div><div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(160px,1fr))',gap:10}}>{similar.slice(0,4).map((s:any)=><a key={s.id} href={`/listing/${s.id}`} style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:12,overflow:'hidden',display:'block',textDecoration:'none'}}><div style={{height:100,background:'var(--bg3)',overflow:'hidden'}}>{s.images?.[0]?<img src={fullImg(s.images[0])} alt="" style={{width:'100%',height:'100%',objectFit:'cover'}}/>:<div style={{height:'100%',display:'flex',alignItems:'center',justifyContent:'center',fontSize:24}}>🚗</div>}</div><div style={{padding:9}}><div style={{fontSize:12,fontWeight:600,color:'var(--text)'}}>{s.year} {s.make} {s.model}</div><div style={{fontSize:13,color:'var(--accent)',fontWeight:700,marginTop:2}}>{s.price?`${fmt(s.price)} €`:'—'}</div></div></a>)}</div></div>}
          </div>

          {/* DESKTOP SIDEBAR — 3 SEKCIJE */}
          <div className="desktop-sidebar" style={{position:'sticky',top:80,display:'flex',flexDirection:'column',gap:0}}>

            {/* SEKCIJA 1: KUPOVINA */}
            <SideSection title="💰 Kupovina">
              <h1 style={{fontSize:16,marginBottom:4,fontFamily:'Syne,sans-serif',fontWeight:700}}>{listing.make} {listing.model}</h1>
              {listing.year&&<div style={{color:'var(--text3)',fontSize:12,marginBottom:8}}>{listing.year} · {fmtKm(listing.mileage)||'—'}</div>}
              <div style={{fontSize:26,fontWeight:800,color:'var(--text)',lineHeight:1,marginBottom:8}}>{price?`${fmt(price)} €`:'Na upit'}</div>
              {listing.price_estimated&&<div style={{background:deltaGood?'rgba(34,197,94,.08)':'rgba(120,113,108,.08)',border:`1px solid ${deltaGood?'rgba(34,197,94,.25)':'rgba(120,113,108,.25)'}`,borderRadius:10,padding:'10px 12px',marginBottom:12}}>
                <div style={{fontSize:11,color:'var(--text3)',marginBottom:3}}>AI procena tržišne vrednosti <span style={{opacity:.6,cursor:'help'}} title="Izračunato iz sličnih oglasa, kilometraže, godišta i opreme.">ⓘ</span></div>
                <div style={{fontWeight:700,fontSize:14}}>{fmt(listing.price_estimated)} €</div>
                <div style={{fontSize:12,color:deltaGood?'#22C55E':'#F87171',marginTop:2}}>{deltaGood?'✅ Ispod':'⚠️ Iznad'} proseka za {Math.abs(Number(listing.price_delta_pct)).toFixed(0)}%</div>
              </div>}
              <a href={listing.url} target="_blank" rel="noopener" className="sdbtn" style={{display:'block',width:'100%',padding:'11px',textAlign:'center',background:'var(--accent)',color:'#fff',borderRadius:10,fontWeight:700,fontSize:14,marginBottom:8,textDecoration:'none'}}>🔗 Pogledaj na {portalName} →</a>
              <button onClick={()=>setShowContact(true)} className="sdbtn" style={{width:'100%',padding:'10px',background:'rgba(99,102,241,.1)',border:'1px solid rgba(99,102,241,.35)',color:'#818CF8',borderRadius:10,fontSize:13,fontWeight:700,cursor:'pointer',marginBottom:8}}>
                🤖 Kontaktiraj prodavca
                <div style={{fontSize:11,fontWeight:400,color:'rgba(129,140,248,.7)',marginTop:2}}>AI generiše poruku na jeziku prodavca</div>
              </button>
              {enriched?<div style={{display:'flex',alignItems:'center',gap:8,background:'rgba(34,197,94,.08)',border:'1px solid rgba(34,197,94,.2)',borderRadius:10,padding:'9px 12px',marginBottom:8}}><span>✅</span><div style={{fontSize:12,fontWeight:600,color:'#22C55E'}}>Podaci provereni od AutoAI</div></div>
              :<button onClick={()=>autoEnrich(listing.url)} disabled={enriching} className="sdbtn" style={{width:'100%',padding:'10px',marginBottom:8,background:enriching?'var(--bg3)':'linear-gradient(135deg,rgba(99,102,241,.15),rgba(99,102,241,.08))',border:`2px solid ${enriching?'var(--border)':'rgba(99,102,241,.4)'}`,color:enriching?'var(--text3)':'#818CF8',borderRadius:10,fontSize:13,fontWeight:700,cursor:enriching?'default':'pointer'}}>
                {enriching?<span style={{display:'flex',alignItems:'center',justifyContent:'center',gap:6}}><span style={{width:7,height:7,borderRadius:'50%',background:'#818CF8',display:'inline-block',animation:'pulse 1s infinite'}}/>Proveravam...</span>
                :<div>🔍 Proveri podatke oglasa<div style={{fontSize:11,fontWeight:400,color:'rgba(129,140,248,.7)',marginTop:2}}>Godište · km · Euro norma</div></div>}
              </button>}
              <div style={{display:'flex',gap:6}}>
                <button className="sdbtn" onClick={()=>{const u=window.location.href;if(navigator.share)navigator.share({title:`${listing.year} ${listing.make} ${listing.model}`,url:u});else{navigator.clipboard.writeText(u);alert('Link kopiran!')}}} style={{flex:1,padding:'8px',background:'transparent',border:'1px solid var(--border)',color:'var(--text2)',borderRadius:9,fontSize:12,cursor:'pointer'}}>🔗 Podeli</button>
                <button className="sdbtn" onClick={handleSave} style={{flex:1,padding:'8px',background:'transparent',border:`1px solid ${favorited?'var(--accent)':'var(--border)'}`,color:favorited?'var(--accent)':'var(--text2)',borderRadius:9,fontSize:12,cursor:'pointer'}}>{favorited?'❤️ Sačuvano':'🤍 Sačuvaj'}</button>
              </div>
            </SideSection>

            {/* SEKCIJA 2: SIGURNOST */}
            <SideSection title="🛡️ Sigurnost kupovine" accent={trust.color}>
              <div onClick={()=>setShowScoreSheet(true)} style={{background:`${trust.color}0d`,border:`1px solid ${trust.color}33`,borderRadius:12,padding:14,cursor:'pointer',marginBottom:fraud?12:0}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:8}}>
                  <div><div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.07em',marginBottom:3}}>AI SCORE</div><div style={{fontSize:11,color:'var(--text3)'}}>Klikni za detalje</div></div>
                  <div style={{textAlign:'right'}}><span style={{fontSize:24,fontWeight:900,color:trust.color}}>{trust.score}</span><span style={{fontSize:11,color:'var(--text3)'}}>/100</span></div>
                </div>
                <div style={{height:5,background:'rgba(255,255,255,.06)',borderRadius:4,overflow:'hidden',marginBottom:8}}><div style={{height:'100%',borderRadius:4,width:`${trust.score}%`,background:trust.color,transition:'width .6s'}}/></div>
                <div style={{fontSize:12,fontWeight:700,color:trust.color,marginBottom:8}}>{trust.label}</div>
                <div style={{display:'flex',flexDirection:'column',gap:3}}>
                  {trust.positives.map((p:any,i:number)=><div key={i} style={{fontSize:11,color:'#22C55E'}}>+ {p.text}</div>)}
                  {trust.negatives.slice(0,3).map((n:any,i:number)=><div key={i} style={{fontSize:11,color:'#F97316'}}>− {n.text}</div>)}
                </div>
              </div>
              {fraud&&<div style={{padding:'10px 12px',background:`${fraud.badge?.color||'#9CA3AF'}11`,border:`1px solid ${fraud.badge?.color||'#9CA3AF'}33`,borderRadius:10}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
                  <div style={{fontSize:12,fontWeight:700}}>Bezbednosna analiza</div>
                  {fraud.badge&&<span style={{fontSize:11,padding:'2px 8px',borderRadius:20,background:`${fraud.badge.color}20`,color:fraud.badge.color,border:`1px solid ${fraud.badge.color}40`}}>{fraud.badge.text}</span>}
                </div>
                {fraud.red_flags?.map((f:string)=><div key={f} style={{fontSize:11,color:'#F87171',marginBottom:2}}>⚠ {f}</div>)}
                {fraud.safe_signals?.map((s:string)=><div key={s} style={{fontSize:11,color:'#22C55E',marginBottom:2}}>✓ {s}</div>)}
              </div>}
            </SideSection>

            {/* SEKCIJA 3: UVOZ U SRBIJU */}
            <SideSection title="🇷🇸 Uvoz u Srbiju" accent={eligColor}>
              <div style={{fontSize:14,fontWeight:800,color:eligColor,marginBottom:4}}>{elig.emoji} {elig.label}</div>
              {elig.sublabel&&<div style={{fontSize:12,color:'var(--text3)',marginBottom:8}}>{elig.sublabel}</div>}
              <p style={{fontSize:12,color:'var(--text2)',margin:'0 0 8px',lineHeight:1.5}}>{elig.reason}</p>
              {elig.warnings.map((w:string,i:number)=><div key={i} style={{fontSize:11,color:'var(--text3)',paddingLeft:8,borderLeft:`2px solid ${eligColor}55`,marginBottom:4,lineHeight:1.4}}>{w}</div>)}
              {bd&&<div style={{marginTop:12,background:'rgba(255,107,0,.07)',border:'1px solid rgba(255,107,0,.2)',borderRadius:10,overflow:'hidden'}}>
                <button onClick={()=>setShowBd(!showBd)} style={{width:'100%',background:'none',border:'none',cursor:'pointer',padding:'10px 12px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <div><div style={{fontSize:10,color:'var(--text3)',marginBottom:1}}>Ukupno za Srbiju</div><div style={{fontSize:17,fontWeight:800,color:'var(--accent)'}}>{fmt(bd.total)} €</div></div>
                  <span style={{fontSize:11,color:'rgba(255,107,0,.6)'}}>{showBd?'▲':'▼ detalji'}</span>
                </button>
                {showBd&&<div style={{padding:'0 12px 10px',borderTop:'1px solid rgba(255,107,0,.15)'}}>
                  {[{label:'EU cena',val:price!,note:''},{label:`Carina (${bd.carinaPct}%)`,val:bd.carina,note:bd.carinaPct===0?'oslobođeno':'srbija'},{label:'PDV (20%)',val:bd.pdv,note:'srbija'},{label:'Transport EU→RS',val:bd.transport,note:'procena'},{label:'Registracija',val:bd.reg,note:'procena'}].map(({label,val,note},i)=>(
                    <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'4px 0',borderTop:i===0?'none':'1px solid rgba(255,255,255,.04)',marginTop:i===0?6:0}}>
                      <span style={{fontSize:11,color:i===0?'var(--text2)':'var(--text3)'}}>{i>0&&'+ '}{label}{note&&<span style={{fontSize:10,marginLeft:3,opacity:.5}}>({note})</span>}</span>
                      <span style={{fontSize:11,fontWeight:600,color:i===0?'var(--text2)':'#fb923c'}}>{i===0?'':'+'}{fmt(val)} €</span>
                    </div>
                  ))}
                  <div style={{display:'flex',justifyContent:'space-between',marginTop:8,paddingTop:8,borderTop:'1px solid rgba(255,107,0,.25)'}}><span style={{fontSize:12,fontWeight:700}}>Ukupno</span><span style={{fontSize:13,fontWeight:800,color:'var(--accent)'}}>{fmt(bd.total)} €</span></div>
                </div>}
              </div>}
              {firstYear&&<div style={{marginTop:12,padding:'10px 12px',background:`${firstYear.color}0d`,border:`1px solid ${firstYear.color}33`,borderRadius:10}}>
                <div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.06em',marginBottom:8}}>PROCENA PRVE GODINE</div>
                {[{label:'Servis',val:firstYear.servis,c:'#22C55E'},{label:'Registracija',val:firstYear.registracija,c:'#22C55E'},{label:'Kvarovi (procena)',val:firstYear.kvarovi,c:'#EF4444'}].map(({label,val,c},i)=>(
                  <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'3px 0'}}><span style={{fontSize:11,color:'var(--text3)'}}>{label}</span><span style={{fontSize:11,fontWeight:600,color:c}}>{fmt(val)} €</span></div>
                ))}
                <div style={{display:'flex',justifyContent:'space-between',marginTop:6,paddingTop:6,borderTop:`1px solid ${firstYear.color}33`}}><span style={{fontSize:12,fontWeight:700}}>Ukupno</span><span style={{fontSize:12,fontWeight:800,color:firstYear.color}}>{fmt(firstYear.total)} €</span></div>
              </div>}
            </SideSection>

          </div>
        </div>
      </div>
    </div>
  )
}

function MobileTabs({listing,elig,eligColor,bd,trust,specs,similar,price,deltaGood,onContact,onShowScore,onShowBd,enriching,enriched,scanMsg,onEnrich,fraud,onVinResult,vinResult,onSave,saved,portalName,firstYear,fuelLabel,kw,ks,images,onGallery}:any){
  const [tab,setTab]=useState(0)
  const TABS=[{icon:'🚗',label:'Vozilo',sub:'Specifikacije'},{icon:'🤖',label:'AI + Uvoz',sub:'Analiza'},{icon:'🔐',label:'VIN',sub:'Provera'}]
  const fmt=(n:any)=>Number(n).toLocaleString('de-DE')
  return(
    <div style={{display:'flex',flexDirection:'column'}}>
      <div style={{display:'flex',gap:5,marginBottom:12,background:'var(--bg2)',borderRadius:12,padding:4,border:'1px solid var(--border)'}}>
        {TABS.map((t,i)=><button key={i} onClick={()=>setTab(i)} style={{flex:1,minHeight:64,borderRadius:9,border:'none',cursor:'pointer',background:tab===i?'linear-gradient(180deg,rgba(255,132,0,.18),rgba(255,132,0,.08))':'transparent',outline:tab===i?'1px solid rgba(255,132,0,.35)':'none',color:tab===i?'var(--accent)':'var(--text3)',transition:'all .18s',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:4,padding:'10px 4px'}}>
          <span style={{fontSize:22,lineHeight:1}}>{t.icon}</span>
          <span style={{fontSize:13,fontWeight:600,lineHeight:1}}>{t.label}</span>
          <span style={{fontSize:10,opacity:.55,lineHeight:1}}>{t.sub}</span>
        </button>)}
      </div>
      <div>
        {tab===0&&<div style={{display:'flex',flexDirection:'column',gap:8}}>
          <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:12,padding:'12px 14px'}}>
            <div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.06em',marginBottom:8}}>SPECIFIKACIJE</div>
            <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:6}}>
              {specs.map((s:any)=><div key={s.label} style={{background:'var(--bg3)',borderRadius:8,padding:'7px 9px'}}>
                <div style={{fontSize:10,color:'var(--text3)',marginBottom:2,letterSpacing:'.04em'}}>{s.label.toUpperCase()}</div>
                <div style={{fontSize:14,fontWeight:700,lineHeight:1.3}}>{s.label==='Grad'?<a href={`https://maps.google.com/?q=${encodeURIComponent([listing.city,listing.country].filter(Boolean).join(', '))}`} target="_blank" rel="noopener" style={{color:'inherit',textDecoration:'none'}}>{s.value} 📍</a>:s.value}</div>
              </div>)}
            </div>
          </div>
          {images?.length>0&&<button onClick={onGallery} style={{width:'100%',padding:'11px',background:'var(--bg2)',border:'1px solid var(--border)',color:'var(--text2)',borderRadius:10,fontSize:13,fontWeight:600,cursor:'pointer',textAlign:'left',display:'flex',justifyContent:'space-between',alignItems:'center'}}><span>🖼️ Sve fotografije ({images.length})</span><span style={{color:'var(--text3)'}}>Otvori →</span></button>}
          {enriched?<div style={{display:'flex',alignItems:'center',gap:8,background:'rgba(34,197,94,.08)',border:'1px solid rgba(34,197,94,.2)',borderRadius:10,padding:'10px 14px'}}><span>✅</span><div style={{fontSize:13,fontWeight:600,color:'#22C55E'}}>Podaci provereni od AutoAI</div></div>
          :!enriching&&listing.url&&<button onClick={onEnrich} style={{width:'100%',padding:'11px 14px',background:'linear-gradient(135deg,rgba(99,102,241,.12),rgba(99,102,241,.06))',border:'1px solid rgba(99,102,241,.3)',color:'#818CF8',borderRadius:10,fontSize:14,fontWeight:600,cursor:'pointer',textAlign:'left'}}>🔍 Proveri podatke oglasa<span style={{fontSize:12,color:'rgba(129,140,248,.6)',display:'block',marginTop:1}}>Godište · km · Euro norma</span></button>}
          {enriching&&<div style={{background:'rgba(99,102,241,.08)',border:'1px solid rgba(99,102,241,.25)',borderRadius:10,padding:'9px 14px',display:'flex',alignItems:'center',gap:8}}><div style={{width:7,height:7,borderRadius:'50%',background:'#818CF8',animation:'pulse 1s infinite',flexShrink:0}}/><span style={{fontSize:13,color:'#818CF8',fontWeight:600}}>{scanMsg}</span></div>}
          {similar.length>0&&<div style={{marginTop:4}}><div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.06em',marginBottom:8}}>SLIČNI OGLASI</div><div style={{display:'flex',gap:8,overflowX:'auto',paddingBottom:4}}>{similar.slice(0,6).map((s:any)=><a key={s.id} href={`/listing/${s.id}`} style={{flexShrink:0,width:130,background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:10,overflow:'hidden',display:'block',textDecoration:'none'}}><div style={{height:75,background:'var(--bg3)',overflow:'hidden'}}>{s.images?.[0]?<img src={s.images[0]} alt="" style={{width:'100%',height:'100%',objectFit:'cover'}}/>:<div style={{height:'100%',display:'flex',alignItems:'center',justifyContent:'center',fontSize:22}}>🚗</div>}</div><div style={{padding:'7px 9px'}}><div style={{fontSize:11,fontWeight:600,color:'var(--text)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{s.year} {s.make} {s.model}</div><div style={{fontSize:12,color:'var(--accent)',fontWeight:700,marginTop:2}}>{s.price?`${fmt(s.price)} €`:'—'}</div></div></a>)}</div></div>}
        </div>}

        {tab===1&&<div style={{display:'flex',flexDirection:'column',gap:8}}>
          <button onClick={onShowScore} style={{width:'100%',background:'var(--bg2)',border:`1px solid ${trust.color}33`,borderRadius:12,padding:'12px 14px',cursor:'pointer',textAlign:'left'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:8}}>
              <div style={{fontSize:10,color:'var(--text3)',fontWeight:600,letterSpacing:'.06em'}}>AI SCORE</div>
              <div><span style={{fontSize:24,fontWeight:800,color:trust.color}}>{trust.score}</span><span style={{fontSize:10,color:'var(--text3)'}}>/100</span></div>
            </div>
            <div style={{height:5,background:'rgba(255,255,255,.06)',borderRadius:4,overflow:'hidden',marginBottom:8}}><div style={{height:'100%',borderRadius:4,width:`${trust.score}%`,background:trust.color,transition:'width .6s'}}/></div>
            <div style={{fontSize:13,fontWeight:700,color:trust.color,marginBottom:6}}>{trust.label}</div>
            <div style={{display:'flex',flexDirection:'column',gap:3}}>
              {trust.positives.slice(0,2).map((p:any,i:number)=><div key={i} style={{fontSize:11,color:'#22C55E'}}>+ {p.text}</div>)}
              {trust.negatives.slice(0,2).map((n:any,i:number)=><div key={i} style={{fontSize:11,color:'#F97316'}}>− {n.text}</div>)}
            </div>
          </button>
          {bd&&<div style={{background:'rgba(255,107,0,.07)',border:'1px solid rgba(255,107,0,.2)',borderRadius:12,padding:'12px 14px'}}>
            <div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.06em',marginBottom:6}}>🇷🇸 TROŠAK UVOZA U SRBIJU</div>
            <div style={{fontSize:22,fontWeight:800,color:'var(--accent)',marginBottom:10}}>{fmt(bd.total)} €</div>
            {[{label:'EU cena',val:price,note:''},{label:`Carina (${bd.carinaPct}%)`,val:bd.carina,note:bd.carinaPct===0?'oslobođeno':'srbija'},{label:'PDV (20%)',val:bd.pdv,note:'srbija'},{label:'Transport EU→RS',val:bd.transport,note:'procena'},{label:'Registracija',val:bd.reg,note:'procena'}].map(({label,val,note},i)=>(
              <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'5px 0',borderTop:i===0?'none':'1px solid rgba(255,255,255,.05)'}}><span style={{fontSize:12,color:i===0?'var(--text2)':'var(--text3)'}}>{i>0&&'+ '}{label}</span><span style={{fontSize:12,fontWeight:600,color:i===0?'var(--text2)':'#fb923c'}}>{fmt(val)} €</span></div>
            ))}
          </div>}
          {firstYear&&<div style={{background:`${firstYear.color}0d`,border:`1px solid ${firstYear.color}33`,borderRadius:12,padding:'12px 14px'}}>
            <div style={{fontSize:10,color:'var(--text3)',fontWeight:700,letterSpacing:'.06em',marginBottom:8}}>PROCENA PRVE GODINE</div>
            {[{label:'Servis',val:firstYear.servis,c:'#22C55E'},{label:'Registracija',val:firstYear.registracija,c:'#22C55E'},{label:'Kvarovi',val:firstYear.kvarovi,c:'#EF4444'}].map(({label,val,c},i)=><div key={i} style={{display:'flex',justifyContent:'space-between',padding:'4px 0'}}><span style={{fontSize:12,color:'var(--text3)'}}>{label}</span><span style={{fontSize:12,fontWeight:600,color:c}}>{fmt(val)} €</span></div>)}
            <div style={{display:'flex',justifyContent:'space-between',marginTop:6,paddingTop:6,borderTop:`1px solid ${firstYear.color}33`}}><span style={{fontSize:13,fontWeight:700}}>Ukupno</span><span style={{fontSize:14,fontWeight:800,color:firstYear.color}}>{fmt(firstYear.total)} €</span></div>
          </div>}
          {fraud&&<div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:12,padding:'12px 14px'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}><div style={{fontSize:12,fontWeight:700}}>🛡️ Bezbednosna provera</div>{fraud.badge&&<span style={{fontSize:11,padding:'2px 8px',borderRadius:20,background:`${fraud.badge.color}20`,color:fraud.badge.color,border:`1px solid ${fraud.badge.color}40`}}>{fraud.badge.text}</span>}</div>
            {fraud.red_flags?.map((f:string)=><div key={f} style={{fontSize:12,color:'#F87171',marginBottom:3}}>⚠ {f}</div>)}
            {fraud.safe_signals?.map((s:string)=><div key={s} style={{fontSize:12,color:'#22C55E',marginBottom:3}}>✓ {s}</div>)}
          </div>}
          {listing.description&&<div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:12,padding:'12px 14px'}}><div style={{fontSize:10,fontWeight:700,marginBottom:8,color:'var(--text3)',letterSpacing:'.06em'}}>OPIS</div><p style={{color:'var(--text2)',lineHeight:1.7,fontSize:13,whiteSpace:'pre-line',margin:0}}>{listing.description.slice(0,600)}{listing.description.length>600?'...':''}</p></div>}
        </div>}

        {tab===2&&<div style={{display:'flex',flexDirection:'column',gap:8}}>
          {listing.make&&<div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:12,padding:'12px 14px'}}><div style={{fontSize:10,fontWeight:700,marginBottom:10,color:'var(--text3)',letterSpacing:'.06em'}}>ŠTA PROVERITI</div><ModelChecklist make={listing.make} model={listing.model} year={listing.year} fuelType={listing.fuel_type} transmission={listing.transmission}/></div>}
          <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:12,padding:'12px 14px'}}>
            <div style={{fontSize:10,fontWeight:700,marginBottom:10,color:'var(--text3)',letterSpacing:'.06em'}}>VIN PROVERA</div>
            <p style={{fontSize:13,color:'var(--text3)',margin:'0 0 12px',lineHeight:1.5}}>Zatraži VIN od prodavca koristeći{' '}<button onClick={onContact} style={{background:'none',border:'none',color:'var(--accent)',cursor:'pointer',fontSize:13,fontWeight:600,padding:0,textDecoration:'underline'}}>Kontaktiraj prodavca</button></p>
            <VinChecker listing={listing} compact onVinResult={onVinResult}/>
          </div>
        </div>}
      </div>
    </div>
  )
}

function PageSkeleton(){
  return(
    <div style={{padding:'12px'}}>
      <div className="skeleton" style={{height:280,borderRadius:14,marginBottom:10}}/>
      <div style={{padding:'0 16px'}}>
        <div className="skeleton" style={{height:32,width:'60%',borderRadius:8,marginBottom:8}}/>
        <div className="skeleton" style={{height:48,width:'40%',borderRadius:8,marginBottom:16}}/>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:10}}>
          <div className="skeleton" style={{height:90,borderRadius:12}}/>
          <div className="skeleton" style={{height:90,borderRadius:12}}/>
        </div>
        <div className="skeleton" style={{height:60,borderRadius:10,marginBottom:8}}/>
        <div className="skeleton" style={{height:120,borderRadius:12}}/>
      </div>
    </div>
  )
}
