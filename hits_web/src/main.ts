import { mount } from 'svelte';
import App from './App.svelte';
import { initLocale, getLocale, subscribeLocale } from './lib/i18n';

// Set <html lang> based on locale, keep it in sync
const htmlEl = document.documentElement;
function updateHtmlLang() {
  htmlEl.setAttribute('lang', getLocale());
}
updateHtmlLang();
subscribeLocale(updateHtmlLang);

const app = mount(App, { target: document.getElementById('app')! });

export default app;
