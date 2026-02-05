import path from "path";

// Project layout:
// nikkei-stock-screener/
//   reports/latest.md
//   universe.csv
//   web-next/

export function projectRoot() {
  return path.resolve(process.cwd(), "..");
}

export function reportsDir() {
  return path.join(projectRoot(), "reports");
}

export function latestReportPath() {
  return path.join(reportsDir(), "latest.md");
}

export function universeCsvPath() {
  return path.join(projectRoot(), "universe.csv");
}
