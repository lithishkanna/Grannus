require('dotenv').config({ path: '.env.local' });

async function checkData() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL + '/rest/v1/pipeline_results?select=*&limit=1';
  const response = await fetch(url, { 
    headers: { 
      apikey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
      Authorization: 'Bearer ' + process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    } 
  });
  const json = await response.json();
  console.log(JSON.stringify(json, null, 2));
}
checkData();
