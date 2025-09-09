'use client';

import React from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { Award, Target, TrendingUp, Clock, Users, Star, Zap, Percent, ShieldCheck, PhoneForwarded, ArrowRight, BookOpen } from 'lucide-react';

// --- API Configuration ---
const API_BASE_URL = "https://sales-enforcer-api.orangeground-02804893.uaenorth.azurecontainerapps.io";
const fetcher = (url: string) => fetch(url).then((res) => res.json());

// --- TYPE DEFINITIONS ---
interface KpiData {
  totalPoints: number;
  quarterlyTarget: number;
  dealsInPipeline: number;
  avgSpeedToClose: number;
  quarterName: string;
}
interface LeaderboardRep {
  id: number;
  name: string;
  avatar: string;
  points: number;
  dealsWon: number;
  onStreak: boolean;
}
interface TimeData {
  week: string;
  points: number;
}
interface Activity {
    id: number;
    type: 'win' | 'stage' | 'bonus';
    text: string;
    time: string;
}
interface SalesHealthData {
    leadToContactedSameDay: number;
    qualToDesignFee: number;
    designFeeCompliance: number;
    proposalToClose: number;
    topLossReasons: { reason: string; value: number }[];
}
interface DashboardData {
    kpis: KpiData;
    leaderboard: LeaderboardRep[];
    pointsOverTime: TimeData[];
    recentActivity: Activity[];
    salesHealth: SalesHealthData;
}

// --- UI COMPONENTS ---
const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
  <div className={`bg-gray-800/50 border border-gray-700/50 rounded-xl shadow-lg backdrop-blur-sm ${className}`}>
    {children}
  </div>
);

const KpiCard = ({ title, value, icon: Icon }: { title: string; value: string | number; icon: React.ElementType }) => (
  <Card className="p-5">
    <div className="flex items-center justify-between">
      <p className="text-sm font-medium text-gray-400">{title}</p>
      <Icon className="h-5 w-5 text-gray-500" />
    </div>
    <div className="mt-2 flex items-baseline">
      <p className="text-3xl font-bold text-white">{value}</p>
    </div>
  </Card>
);

const HealthStatCard = ({ title, value, icon: Icon }: { title: string; value: number; icon: React.ElementType }) => (
    <Card className="p-4">
        <div className="flex items-center">
            <div className="p-3 bg-gray-700/50 rounded-lg"><Icon className="h-6 w-6 text-indigo-400" /></div>
            <div className="ml-4">
                <p className="text-sm text-gray-400">{title}</p>
                <p className="text-2xl font-bold text-white">{value}%</p>
            </div>
        </div>
    </Card>
);

const LoadingSpinner = () => (
    <div className="flex justify-center items-center h-full">
        <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-indigo-500"></div>
    </div>
);

const ErrorDisplay = ({ message }: { message: string }) => (
    <Card className="p-6 bg-red-900/50 border-red-700">
        <h3 className="text-lg font-semibold text-red-200">Error Loading Dashboard</h3>
        <p className="text-red-300 mt-2">{message}</p>
    </Card>
);

// --- MAIN DASHBOARD COMPONENT ---
export default function SalesScorecardDashboard() {
  const { data, error, isLoading } = useSWR<DashboardData>(`${API_BASE_URL}/api/dashboard-data`, fetcher, {
      refreshInterval: 600000 // 10 minutes
  });

  if (isLoading) return <div className="min-h-screen bg-gray-900 flex items-center justify-center"><LoadingSpinner /></div>;
  if (error) return <div className="min-h-screen bg-gray-900 p-8"><ErrorDisplay message={error.message} /></div>;
  if (!data) return <div className="min-h-screen bg-gray-900 p-8"><ErrorDisplay message="No data available." /></div>;

  const { kpis, leaderboard, pointsOverTime, recentActivity, salesHealth } = data;
  const quotaAttainment = kpis.quarterlyTarget > 0 ? ((kpis.totalPoints / kpis.quarterlyTarget) * 100).toFixed(1) : "0.0";

  const activityIcons: { [key: string]: React.ReactNode } = {
    win: <Award className="h-5 w-5 text-yellow-400" />,
    stage: <TrendingUp className="h-5 w-5 text-blue-400" />,
    bonus: <Star className="h-5 w-5 text-pink-400" />,
  };
  const lossReasonColors = ['#8884d8', '#82ca9d', '#ffc658'];

  return (
    <div className="min-h-screen bg-gray-900 text-gray-200 font-sans p-4 sm:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8 flex flex-col sm:flex-row justify-between items-start sm:items-center">
          <div>
            <h1 className="text-3xl font-bold text-white tracking-tight">Sales Scorecard</h1>
            <p className="text-gray-400 mt-1">{kpis.quarterName} Performance Overview</p>
          </div>
          <div className="text-sm text-gray-500 mt-2 sm:mt-0">Last updated: {new Date().toLocaleTimeString()}</div>
        </header>

        {/* ✅ REPLACED WeeklyReport component with a link card */}
        <div className="mb-8">
            <Card className="p-6 group hover:bg-gray-700/50 transition-colors">
                <Link href="/weekly-report" className="flex items-center justify-between">
                    <div className="flex items-center">
                        <div className="p-3 bg-gray-700/50 rounded-lg group-hover:bg-indigo-500/20">
                           <BookOpen className="h-6 w-6 text-indigo-400" />
                        </div>
                        <div className="ml-4">
                            <h2 className="font-semibold text-white">View Weekly Report</h2>
                            <p className="text-sm text-gray-400">See a detailed breakdown of deals created in the last 7 days.</p>
                        </div>
                    </div>
                    <ArrowRight className="h-5 w-5 text-gray-500 group-hover:text-white transition-colors" />
                </Link>
            </Card>
        </div>

        {/* KPI Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <KpiCard title="Total Points (Quarter)" value={kpis.totalPoints.toLocaleString()} icon={Award} />
          <KpiCard title="Quarterly Target" value={kpis.quarterlyTarget.toLocaleString()} icon={Target} />
          <KpiCard title="Deals in Pipeline" value={kpis.dealsInPipeline} icon={Users} />
          <KpiCard title="Avg. Speed-to-Close (Quarter)" value={`${kpis.avgSpeedToClose} days`} icon={Clock} />
        </div>

        {/* ... The rest of your dashboard remains unchanged ... */}
        <div className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">Sales Funnel & Health (All-Time)</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
                <HealthStatCard title="Same-Day Contact" value={salesHealth.leadToContactedSameDay} icon={PhoneForwarded} />
                <HealthStatCard title="Qual to Design Fee" value={salesHealth.qualToDesignFee} icon={Percent} />
                <HealthStatCard title="Fee Compliance" value={salesHealth.designFeeCompliance} icon={ShieldCheck} />
                <HealthStatCard title="Proposal to Close" value={salesHealth.proposalToClose} icon={TrendingUp} />
                <Card className="p-4 sm:col-span-2 lg:col-span-1">
                    <h3 className="text-sm text-gray-400 mb-2">Top Loss Reasons</h3>
                    <ul className="space-y-2">
                        {salesHealth.topLossReasons.map((item, index) => (
                            <li key={item.reason} className="flex items-center justify-between text-sm">
                                <div className="flex items-center">
                                    <div className="h-2.5 w-2.5 rounded-full mr-2" style={{ backgroundColor: lossReasonColors[index] }}></div>
                                    <span className="text-gray-300">{item.reason}</span>
                                </div>
                                <span className="font-bold text-white">{item.value}%</span>
                            </li>
                        ))}
                    </ul>
                </Card>
            </div>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-8">
              <Card className="p-6">
                <h2 className="text-lg font-semibold text-white mb-4">Points Generated (Weekly Trend)</h2>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={pointsOverTime} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
                      <defs><linearGradient id="colorPoints" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#8884d8" stopOpacity={0.8}/><stop offset="95%" stopColor="#8884d8" stopOpacity={0}/></linearGradient></defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#4A5568" />
                      <XAxis dataKey="week" stroke="#A0AEC0" />
                      <YAxis stroke="#A0AEC0" />
                      <Tooltip contentStyle={{ backgroundColor: '#1A202C', borderColor: '#4A5568', color: '#E2E8F0' }} />
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
                    <circle cx="60" cy="60" r="54" fill="none" stroke="#6366F1" strokeWidth="12" strokeDasharray={2 * Math.PI * 54} strokeDashoffset={(2 * Math.PI * 54) * (1 - (parseFloat(quotaAttainment) / 100))} strokeLinecap="round" style={{ transition: 'stroke-dashoffset 0.5s ease-in-out' }} />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center"><span className="text-2xl font-bold text-white">{quotaAttainment}%</span></div>
                </div>
              </Card>
          </div>
          <div className="space-y-8">
              <Card>
                <div className="p-6 border-b border-gray-700"><h2 className="text-lg font-semibold text-white">Leaderboard (Quarterly)</h2></div>
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
                        {rep.onStreak && <span title="On a winning streak!"><Zap className="h-4 w-4 text-yellow-400 mr-2" /></span>}
                        <span className="text-lg font-bold text-indigo-400">{rep.points.toLocaleString()}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
              <Card>
                <div className="p-6 border-b border-gray-700"><h2 className="text-lg font-semibold text-white">Recent Activity</h2></div>
                <ul className="divide-y divide-gray-700">
                  {recentActivity.map((activity) => (
                    <li key={activity.id} className="p-4 flex items-start">
                      <div className="flex-shrink-0 mt-1">{activityIcons[activity.type] || activityIcons.stage}</div>
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