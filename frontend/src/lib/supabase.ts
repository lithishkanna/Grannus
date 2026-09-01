import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://cvnuaxcyadfycsfkeftu.supabase.co'
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN2bnVheGN5YWRmeWNzZmtlZnR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgxOTI2MjIsImV4cCI6MjEwMzc2ODYyMn0.DJ7lRYiJy7W2X0WHoRXi9duF6uBQRiYsJSwa1mDu27I'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
