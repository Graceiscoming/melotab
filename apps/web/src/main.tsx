import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'
import { getTransport } from './audio/instance'
import { useStore } from './store/store'

// ตัวช่วยสำหรับเทสต์ e2e เท่านั้น (ไม่อยู่ใน production build)
if (import.meta.env.DEV) {
  const w = window as unknown as { __melotab: typeof useStore; __getTransport: typeof getTransport }
  w.__melotab = useStore
  w.__getTransport = getTransport // เทสต์ต้องใช้ Transport ตัวเดียวกับแอป (import() ซ้ำใน dev อาจได้โมดูลสำเนาที่สอง)
}

createRoot(document.getElementById('root')!).render(<App />)
