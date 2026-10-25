import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import Workspace from './workspace/Workspace';
import './styles.css';
const demo = new URLSearchParams(window.location.search).has('demo');
createRoot(document.getElementById('root')!).render(<React.StrictMode>{demo ? <App /> : <Workspace />}</React.StrictMode>);
