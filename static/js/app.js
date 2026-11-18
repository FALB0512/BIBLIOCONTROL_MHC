const ICONS={layout:'<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
calendar:'<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
layers:'<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>',
book:'<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/>',
repeat:'<path d="M17 1l4 4-4 4"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><path d="M7 23l-4-4 4-4"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>',
truck:'<path d="M1 3h15v13H1z"/><path d="M16 8h4l3 3v5h-7z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
docsearch:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h6"/><path d="M14 2v6h6"/><circle cx="16.5" cy="16.5" r="3"/><path d="m21 21-1.9-1.9"/>',
chart:'<path d="M3 3v18h18"/><rect x="7" y="12" width="3" height="6"/><rect x="12" y="8" width="3" height="10"/><rect x="17" y="5" width="3" height="13"/>',
users:'<circle cx="9" cy="7" r="4"/><path d="M2 21v-2a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v2"/><path d="M16 3.1a4 4 0 0 1 0 7.8M22 21v-2a4 4 0 0 0-3-3.9"/>',
clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
pencil:'<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
power:'<path d="M18.4 6.6a9 9 0 1 1-12.8 0"/><path d="M12 2v10"/>',
check:'<path d="M20 6 9 17l-5-5"/>',
ban:'<circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/>',
qr:'<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><path d="M14 14h3v3h-3zM20 20h1v1h-1zM17 20h1M20 14v3"/>'};
document.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'+(ICONS[el.dataset.icon]||'')+'</svg>'});
document.querySelectorAll('form[data-confirm]').forEach(form=>form.addEventListener('submit',event=>{if(!window.confirm(form.dataset.confirm)){event.preventDefault()}}));
const SIZE=10;
const tables=[...document.querySelectorAll('.table-wrap')].map(w=>{const f=document.createElement('div');f.className='tbl-foot';w.after(f);return {w,f,page:0}});
function renderTable(t){
  const rows=[...t.w.querySelectorAll('tbody tr')];
  const data=rows.filter(r=>!r.querySelector('td[colspan]'));
  const matched=data.filter(r=>r.dataset.hide!=='1');
  const pages=Math.max(1,Math.ceil(matched.length/SIZE));
  t.page=Math.min(t.page,pages-1);
  data.forEach(r=>{r.style.display='none'});
  matched.slice(t.page*SIZE,(t.page+1)*SIZE).forEach(r=>{r.style.display=''});
  const start=matched.length?t.page*SIZE+1:0;
  const end=Math.min(matched.length,(t.page+1)*SIZE);
  t.f.innerHTML='';
  const info=document.createElement('span');info.textContent='Mostrando '+start+'–'+end+' de '+matched.length+' registros';t.f.append(info);
  if(pages>1){
    const p=document.createElement('div');p.className='pager';
    const btn=(label,page,on,disabled)=>{const b=document.createElement('button');b.textContent=label;b.disabled=disabled;if(on)b.className='on';b.onclick=()=>{t.page=page;renderTable(t)};return b};
    p.append(btn('‹',t.page-1,false,t.page===0));
    for(let i=0;i<pages;i++)p.append(btn(String(i+1),i,i===t.page,false));
    p.append(btn('›',t.page+1,false,t.page>=pages-1));
    t.f.append(p);
  }
}
document.querySelectorAll('input[data-search]').forEach(input=>input.addEventListener('input',()=>{
  const q=input.value.trim().toLowerCase();
  const section=input.closest('section');
  section.querySelectorAll('tbody tr').forEach(row=>{row.dataset.hide=row.textContent.toLowerCase().includes(q)?'':'1'});
  tables.filter(t=>section.contains(t.w)).forEach(t=>{t.page=0;renderTable(t)});
}));
tables.forEach(renderTable);
