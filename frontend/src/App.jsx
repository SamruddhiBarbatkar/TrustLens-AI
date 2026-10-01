import { Route, Routes } from 'react-router-dom'
import { AboutPage } from './pages/AboutPage'
import { AnalyzeImagePage } from './pages/AnalyzeImagePage'
import { DashboardPage } from './pages/DashboardPage'
import { FeaturesPage } from './pages/FeaturesPage'
import { HowItWorksPage } from './pages/HowItWorksPage'
import { HistoryPage } from './pages/HistoryPage'
import { ReportsPage } from './pages/ReportsPage'
import { ResultsPage } from './pages/ResultsPage'
import { ProfilePage } from './pages/ProfilePage'
import { SettingsPage } from './pages/SettingsPage'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { SignupPage } from './pages/SignupPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { AppLayout } from './components/AppLayout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { PublicLayout } from './components/PublicLayout'
import './App.css'

function PublicPage({ children }) {
  return <PublicLayout>{children}</PublicLayout>
}

function PrivatePage({ children }) {
  return <ProtectedRoute><AppLayout>{children}</AppLayout></ProtectedRoute>
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<PublicPage><HomePage /></PublicPage>} />
      <Route path="/login" element={<PublicPage><LoginPage /></PublicPage>} />
      <Route path="/signup" element={<PublicPage><SignupPage /></PublicPage>} />
      <Route path="/features" element={<PublicPage><FeaturesPage /></PublicPage>} />
      <Route path="/how-it-works" element={<PublicPage><HowItWorksPage /></PublicPage>} />
      <Route path="/about" element={<PublicPage><AboutPage /></PublicPage>} />
      <Route path="/dashboard" element={<PrivatePage><DashboardPage /></PrivatePage>} />
      <Route path="/analyze" element={<PrivatePage><AnalyzeImagePage /></PrivatePage>} />
      <Route path="/results/:analysisId" element={<PrivatePage><ResultsPage /></PrivatePage>} />
      <Route path="/history" element={<PrivatePage><HistoryPage /></PrivatePage>} />
      <Route path="/reports" element={<PrivatePage><ReportsPage /></PrivatePage>} />
      <Route path="/profile" element={<PrivatePage><ProfilePage /></PrivatePage>} />
      <Route path="/settings" element={<PrivatePage><SettingsPage /></PrivatePage>} />
      <Route path="*" element={<PublicPage><NotFoundPage /></PublicPage>} />
    </Routes>
  )
}

export default App
