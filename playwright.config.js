const {defineConfig}=require('@playwright/test');
const python=process.env.GOTALEDEN_PYTHON||'python';

module.exports=defineConfig({
  testDir:'./e2e',
  timeout:30_000,
  expect:{timeout:8_000},
  // The lightweight static test server has a small connection backlog on Windows;
  // serial workers keep simultaneous cold page loads deterministic without hiding slow assertions.
  workers:1,
  fullyParallel:false,
  reporter:'line',
  use:{baseURL:'http://127.0.0.1:4173',trace:'retain-on-failure',launchOptions:{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH}},
  webServer:{command:`"${python}" -m http.server 4173 --directory docs`,url:'http://127.0.0.1:4173',reuseExistingServer:true,timeout:20_000,stdout:'ignore',stderr:'ignore'}
});
