require('dotenv').config({ path: '.env.local' });
const fs = require('fs');
async function checkSchema() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL + '/rest/v1/?apikey=' + process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const response = await fetch(url);
  const json = await response.json();
  fs.writeFileSync('schema.json', JSON.stringify(json, null, 2));
}
checkSchema();
