SiteRMAuth.setupAjaxAuth();
$(document).ready(function() {
    load_data();
});

function load_data() {
    var configdata = fetchConfig();
    var sitename = configdata["general"]["sitename"];
    $.ajax({
        url: "/api/" + sitename + "/monitoring/prometheus/metrics",
        dataType: "json",
        data: {},
        async: false,
        success: function(json) {
            json = json[0];
            prometheusOutput = $("<div><\/div>");
            // Loop line by line and add this
            for (var key in json) {
                if (json.hasOwnProperty(key)) {
                    prometheusOutput.append(
                        '<div class="row"><b>' + key + ': <\/b>' + json[key] + "<\/div>"
                    );
                }
            }
            $("#prometheus-metrics").html(prometheusOutput);
        }
    });
}
