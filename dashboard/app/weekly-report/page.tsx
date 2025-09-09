'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { ArrowLeft, AlertCircle, Phone, Mail, ChevronsRight, Briefcase, BarChart3 } from 'lucide-react';

// --- API Configuration & Helper ---
const API_BASE_URL = "https://sales-enforcer-api.orangeground-02804893.uaenorth.azurecontainerapps.io";
const fetcher = (url: string) => fetch(url).then((res) => res.json());

// Helper to format date to YYYY-MM-DD for API
const formatDateForAPI = (date: Date) => {
    return date.toISOString().split('T')[0];
};

// --- TYPE DEFINITIONS ---
interface ActivityDetail { id: number; subject: string; type: string; done: boolean; add_time: string; owner_name: string; }
interface WeeklyDeal { id: number; title: string; owner_name: string; owner_id: number; stage_name: string; value: string; stage_age_days: number; is_stuck: boolean; stuck_reason: string; last_activity_formatted: string; activities: ActivityDetail[]; }
interface SalesUser { id: number; name: string; }
interface StageSummary { stage_name: string; deal_count: number; }
interface ReportSummary { total_deals_created: number; stage_breakdown: StageSummary[]; }
interface WeeklyReportResponse { summary: ReportSummary; deals: WeeklyDeal[]; }

// --- UI COMPONENTS ---
const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
  <div className={`bg-gray-800/50 border border-gray-700/50 rounded-xl shadow-lg backdrop-blur-sm ${className}`}>
    {children}
  </div>
);

const SummaryCard = ({ title, value, icon: Icon }: { title: string, value: string | number, icon: React.ElementType }) => (
    <Card className="p-5">
        <div className="flex items-center">
            <div className="p-3 bg-gray-700/50 rounded-lg"><Icon className="h-6 w-6 text-indigo-400" /></div>
            <div className="ml-4">
                <p className="text-sm text-gray-400">{title}</p>
                <p className="text-3xl font-bold text-white">{value}</p>
            </div>
        </div>
    </Card>
);

const ActivityIcon = ({ type }: { type: string }) => {
    switch (type) {
        case 'call': return <Phone className="h-4 w-4 text-green-400 flex-shrink-0" />;
        case 'email': return <Mail className="h-4 w-4 text-blue-400 flex-shrink-0" />;
        case 'task': return <ChevronsRight className="h-4 w-4 text-purple-400 flex-shrink-0" />;
        default: return <ChevronsRight className="h-4 w-4 text-gray-400 flex-shrink-0" />;
    }
};

const DealRow = ({ deal }: { deal: WeeklyDeal }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    return (
        <>
            <tr onClick={() => setIsExpanded(!isExpanded)} className="border-b border-gray-700 hover:bg-gray-700/50 cursor-pointer transition-colors">
                <td className="px-4 py-3 align-top"><div className="font-medium text-white">{deal.title}</div><div className="text-sm text-gray-400">{deal.owner_name}</div></td>
                <td className="px-4 py-3 text-sm text-gray-300 align-top">{deal.stage_name}</td>
                <td className="px-4 py-3 font-mono text-white align-top">{deal.value}</td>
                <td className="px-4 py-3 align-top"><span className="inline-flex items-center rounded-md bg-gray-600/50 px-2 py-1 text-xs font-medium text-gray-300 ring-1 ring-inset ring-gray-500/10">{deal.stage_age_days} days</span></td>
                <td className="px-4 py-3 text-sm text-gray-400 align-top">{deal.last_activity_formatted}</td>
                <td className="px-4 py-3 align-top">{deal.is_stuck && (<span title={deal.stuck_reason} className="inline-flex items-center gap-x-1.5 rounded-full bg-red-900/80 px-2 py-1 text-xs font-medium text-red-300"><AlertCircle className="h-3 w-3" />Stuck</span>)}</td>
            </tr>
            {isExpanded && (<tr className="bg-gray-800/50"><td colSpan={6} className="p-4"><h4 className="font-semibold text-sm text-white mb-2">Recent Activities ({deal.activities.length})</h4>{deal.activities.length > 0 ? (<ul className="space-y-2">{deal.activities.map(act => (<li key={act.id} className="flex items-center text-sm gap-2"><ActivityIcon type={act.type} /><span className="text-gray-300 flex-grow">{act.subject}</span><span className="text-xs text-gray-500 text-right flex-shrink-0">{new Date(act.add_time).toLocaleDateString()} by {act.owner_name}</span></li>))}</ul>) : (<p className="text-sm text-gray-500">No activities found for this deal.</p>)}</td></tr>)}
        </>
    );
};

const ReportFilters = ({ filters, onFiltersChange }: { filters: any, onFiltersChange: (newFilters: any) => void }) => {
    const { data: users } = useSWR<SalesUser[]>(`${API_BASE_URL}/api/users`, fetcher);

    const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        onFiltersChange({ ...filters, [e.target.name]: e.target.value });
    };

    const handleUserChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        onFiltersChange({ ...filters, userId: e.target.value });
    };

    return (
        <Card className="p-4 mb-8">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
                <div>
                    <label htmlFor="start_date" className="block text-sm font-medium text-gray-300">From Date</label>
                    <input type="date" name="start_date" id="start_date" value={filters.start_date} onChange={handleDateChange} className="mt-1 block w-full bg-gray-700/80 border-gray-600 rounded-md shadow-sm py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm" />
                </div>
                <div>
                    <label htmlFor="end_date" className="block text-sm font-medium text-gray-300">To Date</label>
                    <input type="date" name="end_date" id="end_date" value={filters.end_date} onChange={handleDateChange} className="mt-1 block w-full bg-gray-700/80 border-gray-600 rounded-md shadow-sm py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm" />
                </div>
                <div>
                    <label htmlFor="userId" className="block text-sm font-medium text-gray-300">Salesperson</label>
                    <select id="userId" name="userId" value={filters.userId} onChange={handleUserChange} className="mt-1 block w-full bg-gray-700/80 border-gray-600 rounded-md shadow-sm py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm">
                        <option value="all">All Salespersons</option>
                        {users && users.map(user => (<option key={user.id} value={user.id}>{user.name}</option>))}
                    </select>
                </div>
            </div>
        </Card>
    );
};

export default function WeeklyReportPage() {
    const [filters, setFilters] = useState({
        start_date: formatDateForAPI(new Date(new Date().setDate(new Date().getDate() - 6))),
        end_date: formatDateForAPI(new Date()),
        userId: 'all'
    });

    // Build the URL with query parameters for SWR
    const queryParams = new URLSearchParams({
        start_date: filters.start_date,
        end_date: filters.end_date,
    });
    if (filters.userId !== 'all') {
        queryParams.append('user_id', filters.userId);
    }
    const reportUrl = `${API_BASE_URL}/api/weekly-report?${queryParams.toString()}`;

    const { data, error, isLoading } = useSWR<WeeklyReportResponse>(reportUrl, fetcher);

    return (
        <div className="min-h-screen bg-gray-900 text-gray-200 font-sans p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto">
                <header className="mb-8 flex justify-between items-center">
                    <h1 className="text-3xl font-bold text-white tracking-tight">Deals Created Report</h1>
                    <Link href="/" className="inline-flex items-center text-indigo-400 hover:text-indigo-300 transition-colors">
                        <ArrowLeft className="h-4 w-4 mr-2" />
                        Back to Main Dashboard
                    </Link>
                </header>
                <main>
                    <ReportFilters filters={filters} onFiltersChange={setFilters} />
                    
                    {isLoading && <div className="p-8 text-center text-gray-400">Loading report...</div>}
                    {error && <div className="p-8 text-center text-red-400">Failed to load report. Please try again.</div>}
                    
                    {data && (
                        <>
                            {/* Section 1: Summary View */}
                            <div className="mb-8">
                                <h2 className="text-xl font-semibold text-white mb-4">Summary</h2>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                    <SummaryCard title="Total Deals Created" value={data.summary.total_deals_created} icon={Briefcase} />
                                    <Card className="p-5 md:col-span-2">
                                        <div className="flex items-center mb-3">
                                            <div className="p-2 bg-gray-700/50 rounded-lg"><BarChart3 className="h-5 w-5 text-indigo-400" /></div>
                                            <h3 className="ml-3 text-sm text-gray-400">Breakdown by Stage</h3>
                                        </div>
                                        {data.summary.stage_breakdown.length > 0 ? (
                                             <ul className="space-y-2">
                                                {data.summary.stage_breakdown.map(stage => (
                                                    <li key={stage.stage_name} className="flex justify-between items-center text-sm">
                                                        <span className="text-gray-300">{stage.stage_name}</span>
                                                        <span className="font-bold text-white bg-gray-700/60 px-2 py-0.5 rounded-md">{stage.deal_count}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        ) : <p className="text-sm text-gray-500">No deals to summarize.</p>}
                                    </Card>
                                </div>
                            </div>

                            {/* Section 2: Detailed Deal List */}
                            <Card>
                                <div className="p-6 border-b border-gray-700">
                                     <h2 className="text-xl font-semibold text-white">Detailed List</h2>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left">
                                        <thead className="bg-gray-800/60 text-xs text-gray-400 uppercase tracking-wider">
                                            <tr>
                                                <th className="px-4 py-3 font-medium">Deal / Owner</th>
                                                <th className="px-4 py-3 font-medium">Current Stage</th>
                                                <th className="px-4 py-3 font-medium">Value</th>
                                                <th className="px-4 py-3 font-medium">Time in Stage</th>
                                                <th className="px-4 py-3 font-medium">Last Activity</th>
                                                <th className="px-4 py-3 font-medium">Status</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-800">
                                            {data.deals.length > 0 ? (
                                                data.deals.map(deal => <DealRow key={deal.id} deal={deal} />)
                                            ) : (
                                                <tr><td colSpan={6} className="text-center py-8 text-gray-500">No deals created in the selected period.</td></tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            </Card>
                        </>
                    )}
                </main>
            </div>
        </div>
    );
}