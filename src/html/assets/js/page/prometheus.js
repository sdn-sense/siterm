SiteRMAuth.setupAjaxAuth();
$(document).ready(function() {
    load_data();
});

function load_data() {
    const configdata = fetchConfig();
    const sitename = configdata["general"]["sitename"];

    $.ajax({
        url: "/api/" + sitename + "/monitoring/prometheus/metrics",
        dataType: "text",          // <-- this is the key change
        async: true,               // don't block the browser
        error: function (xhr, status, error) {
            const url = "/api/" + sitename + "/monitoring/prometheus/metrics";

            const details = `
        HTTP ${xhr.status} – ${error}
        URL: ${url}
        Response: ${xhr.responseText || "<empty>"}
        Headers: ${xhr.getAllResponseHeaders?.() || "<none>"}
            `.trim();

            showAjaxWarning(
                "Failed to load Prometheus metrics",
                details
            );

            console.error("AJAX ERROR DETAILS:", {
                url: url,
                status: xhr.status,
                statusText: xhr.statusText,
                error: error,
                response: xhr.responseText,
                headers: xhr.getAllResponseHeaders?.()
            });
        },
        success: function (text) {
            const prometheusOutput = $("<div></div>");

            // Prometheus format is line-based
            text.split("\n").forEach(line => {
                if (!line.trim()) return;

                // Comments start with #
                if (line.startsWith("#")) {
                    prometheusOutput.append(
                        `<div class="text-muted small">${escapeHtml(line)}</div>`
                    );
                } else {
                    prometheusOutput.append(
                        `<div><code>${escapeHtml(line)}</code></div>`
                    );
                }
            });

            $("#prometheus-metrics").empty().append(prometheusOutput);
        }
    });
}