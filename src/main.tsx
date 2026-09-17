import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { CustomerApp } from './apps/customer/CustomerApp'
import { ManagerApp } from './apps/manager/ManagerApp'
import './styles/global.css'

const isManagerRoute = window.location.pathname.toLowerCase().startsWith('/manager')
const App = isManagerRoute ? ManagerApp : CustomerApp

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
