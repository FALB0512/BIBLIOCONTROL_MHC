document.querySelectorAll('form[data-confirm]').forEach(form=>form.addEventListener('submit',event=>{if(!window.confirm(form.dataset.confirm)){event.preventDefault()}}));
document.querySelectorAll('input[data-search]').forEach(input=>input.addEventListener('input',()=>{const t=input.value.trim().toLowerCase();input.closest('section').querySelectorAll('tbody tr').forEach(row=>{row.style.display=row.textContent.toLowerCase().includes(t)?'':'none'})}));
const tableFoots=[...document.querySelectorAll('.table-wrap')].map(w=>{const f=document.createElement('div');f.className='tbl-foot';w.after(f);return [w,f]});
const updateFoots=()=>tableFoots.forEach(([w,f])=>{const n=[...w.querySelectorAll('tbody tr')].filter(r=>r.style.display!=='none'&&!r.querySelector('td[colspan]')).length;f.textContent='Mostrando '+n+' registros'});
document.addEventListener('input',updateFoots);updateFoots();
