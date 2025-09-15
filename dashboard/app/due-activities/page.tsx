'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { ArrowLeft, Phone, Mail, ChevronsRight, Calendar, AlertTriangle } from 'lucide-react';

// --- API Configuration & Helper ---
const API_BASE_URL = "https://sales-enforcer-api.orangeground-02804893.uaenorth.azurecontainerapps.io";
const fetcher = (url: string) => fetch(url).then((res) => res.json());

const formatDateForAPI = (date: Date) => {
    return date.toISOString().split('T')[0];
};

// --- TYPE DEFINITIONS ---
interface DueActivity {
    id: number;
    subject: string;
    type: string;
    due_date: string;
    owner_name: string;
    deal_id?: number;
    deal_title?: string;
    is_overdue: boolean;
}

interface SalesUser { id: number; name: string; }

interface DueActivityFiltersState {
  start_date: string;
  end_date: string;
  userId: string;
}

// --- UI COMPONENTS ---
const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
  <div className={`bg-gray-800/50 border border-gray-700/50 rounded-xl shadow-lg backdrop-blur-sm ${className}`}>
    {children}
  </div>
);

const ActivityIcon = ({ type }: { type: string }) => {
    switch (type) {
        case 'call': return <Phone className="h-4 w-4 text-green-400 flex-shrink-0" />;
        case 'email': return <Mail className="h-4 w-4 text-blue-400 flex-shrink-0" />;
        case 'task': return <ChevronsRight className="h-4 w-4 text-purple-400 flex-shrink-0" />;
        default: return <ChevronsRight className="h-4 w-4 text-gray-400 flex-shrink-0" />;
    }
};

const Filters = ({ filters, onFiltersChange }: { filters: DueActivityFiltersState, onFiltersChange: (newFilters: DueActivityFiltersState) => void }) => {
    const { data: users } = useSWR<SalesUser[]>(`${API_BASE_URL}/api/users`, fetcher);

    return (
        <Card className="p-4 mb-8">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
                <div>
                    <label htmlFor="start_date" className="block text-sm font-medium text-gray-300">Due From</label>
                    <input type="date" name="start_date" id="start_date" value={filters.start_date} onChange={e => onFiltersChange({ ...filters, [e.target.name]: e.target.value })} className="mt-1 block w-full bg-gray-700/80 border-gray-600 rounded-md shadow-sm py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm" />
                </div>
                <div>
                    <label htmlFor="end_date" className="block text-sm font-medium text-gray-300">Due To</label>
                    <input type="date" name="end_date" id="end_date" value={filters.end_date} onChange={e => onFiltersChange({ ...filters, [e.target.name]: e.target.value })} className="mt-1 block w-full bg-gray-700/80 border-gray-600 rounded-md shadow-sm py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm" />
                </div>
                <div>
                    <label htmlFor="userId" className="block text-sm font-medium text-gray-300">Salesperson</label>
                    <select id="userId" name="userId" value={filters.userId} onChange={e => onFiltersChange({ ...filters, userId: e.target.value })} className="mt-1 block w-full bg-gray-700/80 border-gray-600 rounded-md shadow-sm py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm">
                        <option value="all">All Salespersons</option>
                        {users && users.map(user => (<option key={user.id} value={user.id}>{user.name}</option>))}
                    </select>
                </div>
            </div>
        </Card>
    );
};

export default function DueActivitiesPage() {
    // ✅ CHANGED: Updated the initial state for the date filters.
    const getInitialFilters = () => {
        const today = new Date();
        const oneMonthAgo = new Date();
        oneMonthAgo.setMonth(today.getMonth() - 1);

        return {
            start_date: formatDateForAPI(oneMonthAgo), // Defaults to one month ago
            end_date: formatDateForAPI(today),       // Defaults to today
            userId: 'all'
        };
    };

    const [filters, setFilters] = useState<DueActivityFiltersState>(getInitialFilters());

    const queryParams = new URLSearchParams({
        start_date: filters.start_date,
        end_date: filters.end_date,
    });
    if (filters.userId !== 'all') {
        queryParams.append('user_id', filters.userId);
    }
    const reportUrl = `${API_BASE_URL}/api/due-activities?${queryParams.toString()}`;

    const { data: activities, error, isLoading } = useSWR<DueActivity[]>(reportUrl, fetcher);

    return (
        <div className="min-h-screen bg-gray-900 text-gray-200 font-sans p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto">
                <header className="mb-8 flex justify-between items-center">
                    <h1 className="text-3xl font-bold text-white tracking-tight">Due Activities Report</h1>
                    <Link href="/" className="inline-flex items-center text-indigo-400 hover:text-indigo-300 transition-colors">
                        <ArrowLeft className="h-4 w-4 mr-2" />
                        Back to Main Dashboard
                    </Link>
                </header>
                <main>
                    <Filters filters={filters} onFiltersChange={setFilters} />
                    
                    <Card>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left">
                                <thead className="bg-gray-800/60 text-xs text-gray-400 uppercase tracking-wider">
                                    <tr>
                                        <th className="px-4 py-3 font-medium">Activity Subject</th>
                                        <th className="px-4 py-3 font-medium">Related Deal</th>
                                        <th className="px-4 py-3 font-medium">Due Date</th>
                                        <th className="px-4 py-3 font-medium">Owner</th>
                                        <th className="px-4 py-3 font-medium">Status</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-800">
                                    {isLoading && <tr><td colSpan={5} className="text-center py-8 text-gray-400">Loading activities...</td></tr>}
                                    {error && <tr><td colSpan={5} className="text-center py-8 text-red-400">Failed to load activities.</td></tr>}
                                    {activities && activities.length > 0 ? (
                                        activities.map(act => (
                                            <tr key={act.id}>
                                                <td className="px-4 py-3">
                                                    <div className="flex items-center">
                                                        <ActivityIcon type={act.type} />
                                                        <span className="ml-3 font-medium text-white">{act.subject}</span>
                                                    </div>
                                                </td>
                                                <td className="px-4 py-3 text-sm text-gray-400">{act.deal_title}</td>
                                                <td className="px-4 py-3 text-sm text-gray-300">{new Date(act.due_date + 'T00:00:00').toLocaleDateString()}</td>
                                                <td className="px-4 py-3 text-sm text-gray-400">{act.owner_name}</td>
                                                <td className="px-4 py-3">
                                                    {act.is_overdue && (
                                                        <span className="inline-flex items-center gap-x-1.5 rounded-full bg-yellow-900/80 px-2 py-1 text-xs font-medium text-yellow-300">
                                                            <AlertTriangle className="h-3 w-3" />
                                                            Overdue
                                                        </span>
                                                    )}
                                                </td>
                                            </tr>
                                        ))
                                    ) : (
                                       !isLoading && <tr><td colSpan={5} className="text-center py-8 text-gray-500">No due activities found for the selected filters.</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </Card>
                </main>
            </div>
        </div>
    );
}