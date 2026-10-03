import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'
import { useStore } from './store/store'

// ตัวช่วยสำหรับเทสต์ e2e เท่านั้น (ไม่อยู่ใน production build)
if (import.meta.env.DEV) (window as unknown as { __melotab: typeof useStore }).__melotab = useStore

createRoot(document.getElementById('root')!).render(<App />)
