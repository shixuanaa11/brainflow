import { Routes, Route } from 'react-router-dom'
import Layout from '@/components/layout/Layout'
import OverviewPage from '@/pages/overview/OverviewPage'
import TracesPage from '@/pages/traces/TracesPage'
import GraphPage from '@/pages/graph/GraphPage'
import ChatPage from '@/pages/chat/ChatPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/traces" element={<TracesPage />} />
        <Route path="/graph" element={<GraphPage />} />
        <Route path="/chat" element={<ChatPage />} />
      </Route>
    </Routes>
  )
}