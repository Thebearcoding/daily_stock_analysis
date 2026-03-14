import type React from 'react';
import {BrowserRouter as Router, Routes, Route, NavLink} from 'react-router-dom';
import HomePage from './pages/HomePage';
import FundAdvicePage from './pages/FundAdvicePage';
import NotFoundPage from './pages/NotFoundPage';
import { AppErrorBoundary } from './components/common';
import './App.css';

type DockItem = {
    key: string;
    label: string;
    to: string;
};

const NAV_ITEMS: DockItem[] = [
    {
        key: 'home',
        label: '股票',
        to: '/',
    },
    {
        key: 'funds',
        label: '基金',
        to: '/funds',
    },
];

const App: React.FC = () => {
    return (
        <Router>
            <div className="app-shell">
                <header className="app-header">
                    <div className="app-header-inner">
                        <div className="app-brand">
                            <div className="app-brand-dot" />
                            <div>
                                <p className="app-brand-title">Daily Stock Analysis</p>
                                <p className="app-brand-subtitle">更清晰的股票与基金决策工作台</p>
                            </div>
                        </div>

                        <nav className="app-nav" aria-label="页面导航">
                            {NAV_ITEMS.map((item) => (
                                <NavLink
                                    key={item.key}
                                    to={item.to}
                                    end={item.to === '/'}
                                    className={({isActive}) => `app-nav-item${isActive ? ' is-active' : ''}`}
                                >
                                    {item.label}
                                </NavLink>
                            ))}
                        </nav>
                    </div>
                </header>

                <main className="app-main">
                    <AppErrorBoundary>
                        <Routes>
                            <Route path="/" element={<HomePage/>}/>
                            <Route path="/funds" element={<FundAdvicePage/>}/>
                            <Route path="*" element={<NotFoundPage/>}/>
                        </Routes>
                    </AppErrorBoundary>
                </main>
            </div>
        </Router>
    );
};

export default App;
