import { useState } from 'react'

function App() {
  const [health, setHealth] = useState<string | null>(null)

  async function checkHealth() {
    try {
      const res = await fetch('/api/health')
      const data = await res.json()
      setHealth(`${data.status} — v${data.version}`)
    } catch {
      setHealth('Backend unreachable')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-6">
      <h1 className="text-3xl font-bold text-gray-800">Bob the Onboarder</h1>
      <p className="text-gray-500 text-sm">Repository intelligence powered by IBM Bob 2.0</p>
      <button
        onClick={checkHealth}
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
      >
        Ping Backend
      </button>
      {health && (
        <p className="text-sm font-mono bg-white border border-gray-200 rounded px-3 py-1 text-gray-700">
          {health}
        </p>
      )}
    </div>
  )
}

export default App
