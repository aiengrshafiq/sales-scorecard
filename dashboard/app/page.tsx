// You need to install these dependencies in your Next.js project:
// npm install recharts lucide-react clsx tailwind-merge

'use client'; // <-- THIS IS THE FIX. It tells Next.js to render this component in the browser.

import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { Award, Target, TrendingUp, Clock, Users, Star, CheckCircle, Zap } from 'lucide-react';

// --- DUMMY DATA (Simulating API Response) ---
const dummyData = {
  kpis: {
    totalPoints: 8740,
    quarterlyTarget: 15000,
    dealsInPipeline: 76,
    avgSpeedToClose: 18, // in days
  },
  leaderboard: [
    { id: 1, name: 'Aisha Al-Farsi', avatar: 'https://i.pravatar.cc/150?u=aisha', points: 2150, dealsWon: 5, onStreak: true },
    { id: 2, name: 'Shafiq Ahmed', avatar: 'https://i.pravatar.cc/150?u=shafiq', points: 1980, dealsWon: 4, onStreak: false },
    { id: 3, name: 'Fatima Khan', avatar: 'https://i.pravatar.cc/150?u=fatima', points: 1820, dealsWon: 6, onStreak: true },
    { id: 4, name: 'Yusuf Al-Mansoori', avatar: 'https://i.pravatar.cc/150?u=yusuf', points: 1550, dealsWon: 3, onStreak: false },
    { id: 5, name: 'Layla Ibrahim', avatar: 'https://i.pravatar.cc/150?u=layla', points: 1240, dealsWon: 2, onStreak: false },
  ],
  pointsOverTime: [
    { week: 'W1', points: 400 }, { week: 'W2', points: 650 }, { week: 'W3', points: 500 },
    { week: 'W4', points: 800 }, { week: 'W5', points: 750 }, { week: 'W6', points: 900 },
    { week: 'W7', points: 1100 }, { week: 'W8', points: 1250 }, { week: 'W9', points: 1440 },
  ],
  dealStageDistribution: [
    { name: 'Lead Intake', value: 25 },
    { name: 'Qualification', value: 20 },
    { name: 'Design Intake', value: 15 },
    { name: 'Proposal', value: 10 },
    { name: 'Close', value: 6 },
  ],
  recentActivity: [
    { id: 1, type: 'win', text: 'Aisha Al-Farsi won "Project Phoenix" for 200 pts.', time: '2m ago' },
    { id: 2, type: 'stage', text: 'Shafiq Ahmed moved "Delta Initiative" to Proposal.', time: '15m ago' },
    { id: 3, type: 'bonus', text: 'Fatima Khan earned a "Fast Close" bonus for 50 pts.', time: '1h ago' },
    { id: 4, type: 'stage', text: 'A new deal "Omega Solutions" entered Lead Intake.', time: '3h ago' },
    { id: 5, type: 'win', text: 'Yusuf Al-Mansoori won "Global Connect" for 100 pts.', time: '5h ago' },
  ],
};

// --- HELPER COMPONENTS ---

// A reusable card component for a consistent look
const Card = ({ children, className = '' }) => (
  <div className={`bg-gray-800/50 border border-gray-700/50 rounded-xl shadow-lg backdrop-blur-sm ${className}`}>
    {children}
  </div>
);

// KPI Card Component
const KpiCard = ({ title, value, icon: Icon, change }) => (
  <Card className="p-5">
    <div className="flex items-center justify-between">
      <p className="text-sm font-medium text-gray-400">{title}</p>
      <Icon className="h-5 w-5 text-gray-500" />
    </div>
    <div className="mt-2 flex items-baseline">
      <p className="text-3xl font-bold text-white">{value}</p>
      {change && (
        <p className="ml-2 text-sm font-semibold text-green-400">{change}</p>
      )}
    </div>
  </Card>
);

// --- MAIN DASHBOARD COMPONENT ---

export default function SalesScorecardDashboard() {
  const { kpis, leaderboard, pointsOverTime, recentActivity } = dummyData;
  const quotaAttainment = ((kpis.totalPoints / kpis.quarterlyTarget) * 100).toFixed(1);

  const activityIcons = {
    win: <Award className="h-5 w-5 text-yellow-400" />,
    stage: <TrendingUp className="h-5 w-5 text-blue-400" />,
    bonus: <Star className="h-5 w-5 text-pink-400" />,
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-200 font-sans p-4 sm:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto">
        
        {/* Header */}
        <header className="mb-8 flex flex-col sm:flex-row justify-between items-start sm:items-center">
          <div>
            <h1 className="text-3xl font-bold text-white tracking-tight">Sales Scorecard</h1>
            <p className="text-gray-400 mt-1">Q3 2025 Performance Overview</p>
          </div>
          <div className="text-sm text-gray-500 mt-2 sm:mt-0">
            Last updated: {new Date().toLocaleTimeString()}
          </div>
        </header>

        {/* KPI Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <KpiCard title="Total Points (Quarter)" value={kpis.totalPoints.toLocaleString()} icon={Award} change="+12% MoM" />
          <KpiCard title="Quarterly Target" value={kpis.quarterlyTarget.toLocaleString()} icon={Target} />
          <KpiCard title="Deals in Pipeline" value={kpis.dealsInPipeline} icon={Users} />
          <KpiCard title="Avg. Speed-to-Close" value={`${kpis.avgSpeedToClose} days`} icon={Clock} />
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Left Column: Main Chart + Quota */}
          <div className="lg:col-span-2 space-y-8">
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-white mb-4">Points Generated (Weekly)</h2>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={pointsOverTime} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
                    <defs>
                      <linearGradient id="colorPoints" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#8884d8" stopOpacity={0.8}/>
                        <stop offset="95%" stopColor="#8884d8" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#4A5568" />
                    <XAxis dataKey="week" stroke="#A0AEC0" />
                    <YAxis stroke="#A0AEC0" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1A202C',
                        borderColor: '#4A5568',
                        color: '#E2E8F0',
                      }}
                    />
                    <Area type="monotone" dataKey="points" stroke="#8884d8" fillOpacity={1} fill="url(#colorPoints)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card className="p-6 flex flex-col sm:flex-row items-center justify-between">
                <div>
                    <h3 className="text-lg font-semibold text-white">Quarterly Target Attainment</h3>
                    <p className="text-gray-400 text-sm mt-1">Progress towards the quarterly points goal.</p>
                </div>
                <div className="relative mt-4 sm:mt-0">
                    <svg className="transform -rotate-90" width="120" height="120" viewBox="0 0 120 120">
                        <circle cx="60" cy="60" r="54" fill="none" stroke="#4A5568" strokeWidth="12" />
                        <circle
                            cx="60"
                            cy="60"
                            r="54"
                            fill="none"
                            stroke="#6366F1"
                            strokeWidth="12"
                            strokeDasharray={2 * Math.PI * 54}
                            strokeDashoffset={(2 * Math.PI * 54) * (1 - (parseFloat(quotaAttainment) / 100))}
                            strokeLinecap="round"
                            style={{ transition: 'stroke-dashoffset 0.5s ease-in-out' }}
                        />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-2xl font-bold text-white">{quotaAttainment}%</span>
                    </div>
                </div>
            </Card>
          </div>

          {/* Right Column: Leaderboard + Activity */}
          <div className="space-y-8">
            <Card>
              <div className="p-6 border-b border-gray-700">
                <h2 className="text-lg font-semibold text-white">Leaderboard</h2>
              </div>
              <ul className="divide-y divide-gray-700">
                {leaderboard.map((rep, index) => (
                  <li key={rep.id} className="p-4 flex items-center justify-between hover:bg-gray-700/30 transition-colors">
                    <div className="flex items-center">
                      <span className="text-lg font-bold text-gray-400 w-6">{index + 1}</span>
                      <img className="h-10 w-10 rounded-full ml-4" src={rep.avatar} alt={rep.name} />
                      <div className="ml-4">
                        <p className="font-semibold text-white">{rep.name}</p>
                        <p className="text-sm text-gray-400">{rep.dealsWon} deals won</p>
                      </div>
                    </div>
                    <div className="text-right flex items-center">
                        {rep.onStreak && <Zap className="h-4 w-4 text-yellow-400 mr-2" title="On a winning streak!" />}
                        <span className="text-lg font-bold text-indigo-400">{rep.points.toLocaleString()}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>

            <Card>
              <div className="p-6 border-b border-gray-700">
                <h2 className="text-lg font-semibold text-white">Recent Activity</h2>
              </div>
              <ul className="divide-y divide-gray-700">
                {recentActivity.map((activity) => (
                  <li key={activity.id} className="p-4 flex items-start">
                    <div className="flex-shrink-0 mt-1">
                      {activityIcons[activity.type]}
                    </div>
                    <div className="ml-4">
                      <p className="text-sm text-gray-300">{activity.text}</p>
                      <p className="text-xs text-gray-500 mt-1">{activity.time}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
