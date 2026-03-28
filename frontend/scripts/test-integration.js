#!/usr/bin/env node
/**
 * Frontend integration test: Verify all API endpoints work and data flows correctly.
 * Run with: node frontend/scripts/test-integration.js
 */

const API_BASE = process.env.API_BASE || "http://localhost:8000/api/v1";

async function fetchJson(endpoint) {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    return null;
  }
}

async function main() {
  console.log("🧪 JUDICIARY TRACKER: FRONTEND INTEGRATION TEST");
  console.log(`API Base: ${API_BASE}\n`);

  const tests = [
    { name: "System Status", endpoint: "/status/integration-ready" },
    { name: "Court Stats", endpoint: "/stats/court" },
    { name: "Cases List", endpoint: "/cases?page=1&page_size=5" },
    { name: "Judges", endpoint: "/judges" },
    { name: "Flags", endpoint: "/flags?page=1&page_size=5" },
    { name: "Datasets", endpoint: "/datasets" },
    { name: "Population Runs", endpoint: "/admin/population/runs?limit=1" },
  ];

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    process.stdout.write(`  ${test.name:20} ... `);
    const data = await fetchJson(test.endpoint);
    if (data !== null) {
      console.log("✓");
      passed++;

      // For status endpoint, show key info
      if (test.endpoint === "/status/integration-ready") {
        console.log(`    └─ Ready for interface: ${data.ready_for_interface ? "YES" : "NO"} | Cases: ${data.total_cases} | Sources: ${data.active_sources}`);
        if (data.last_population_run) {
          console.log(
            `    └─ Last run: ${data.last_population_run.run_id} (${data.last_population_run.status}) | ${data.last_population_run.completed_sources}/${data.last_population_run.total_sources} sources`
          );
        }
      }

      // For cases, show count
      if (test.endpoint.includes("/cases") && !test.endpoint.includes("/{")) {
        const count = data.items?.length || 0;
        const total = data.total || 0;
        if (count > 0) {
          console.log(`    └─ Found ${count} cases (total: ${total})`);
        }
      }
    } else {
      console.log("✗");
      failed++;
      console.log(`    └─ Error fetching ${test.endpoint}`);
    }
  }

  console.log(`\n📊 RESULTS: ${passed} passed, ${failed} failed`);

  if (failed === 0 && passed > 0) {
    console.log("✅ All tests passed! Frontend ready to display data.\n");
    console.log("🎯 Next steps:");
    console.log("  1. Open http://localhost:3000/hub");
    console.log("  2. Check 'Overview' section for court statistics");
    console.log("  3. Use 'Case Search' to query populated cases");
    console.log("  4. Visit 'Population' section to monitor ingestion runs");
    process.exit(0);
  } else {
    console.log(
      "\n⚠️  Some tests failed. Check that:\n" +
      "  - Backend is running (docker ps)\n" +
      "  - Database has data (docker exec justice-tracker-db psql ...)\n" +
      "  - Population run has completed or has records\n"
    );
    process.exit(1);
  }
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
