import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import RequireAuth from './components/RequireAuth'
import Home from './pages/Home'
import Results from './pages/Results'
import Login from './pages/Login'
import Signup from './pages/Signup'

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="min-h-screen bg-background">
          <Routes>
            <Route path="/login"  element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/"                  element={<RequireAuth><Home /></RequireAuth>} />
            <Route path="/results/:jobId"    element={<RequireAuth><Results /></RequireAuth>} />
          </Routes>
        </div>
      </Router>
    </AuthProvider>
  )
}

export default App
