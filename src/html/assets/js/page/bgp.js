SiteRMAuth.setupAjaxAuth();
$(document).ready(function() {
    load_data();
});

var bgpRows = [];

function prettyJson(dataIn, saveObj) {
    var text;
    try {
        text = JSON.stringify(dataIn, null, 2);
    } catch (e) {
        text = String(dataIn);
    }
    saveObj.append($("<pre></pre>").text(text));
}

function loadBgpHost(idx, sitename) {
    var row = bgpRows[idx];
    var output = row["output"];
    if (typeof output === "string") {
        try {
            output = JSON.parse(output);
        } catch (e) {
            // Leave as raw string if it does not parse -- still shown below.
        }
    }

    var model = $("<div></div>");
    model.append('<div class="row"><b>Hostname: </b>' + row["hostname"] + "</div>");
    model.append(
        '<div class="row"><b>Last Updated: </b>' +
        new Date(row["updatedate"] * 1000).toLocaleString() +
        "</div>",
    );
    model.append('<div class="row"><b>BGP Summary:</b></div>');
    prettyJson(output, model);

    $("#v-pills-" + row["id"])
        .empty()
        .append(model);
}

function forceBgpRescan(sitename) {
    SiteRMAuth.authFetch("/api/" + sitename + "/monitoring/bgpstats/rescan", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({}),
        })
        .then(async (response) => {
            const text = await response.text();

            if (!response.ok) {
                throw {
                    status: response.status,
                    message: text,
                };
            }

            return text ? JSON.parse(text) : {};
        })
        .then((result) => {
            newAlert("BGP rescan requested: " + JSON.stringify(result), {
                type: "main"
            });
        })
        .catch((err) => {
            showAjaxWarning(
                "Failed to request BGP rescan",
                `HTTP ${err.status || "?"} – ${err.message || err}`
            );
            console.error("Fetch error:", err);
        });
}

function defineAllBgp(data, sitename) {
    bgpRows = data;
    var rescanRow = $('<div class="row mb-2">').append(
        '<div class="col-auto"><button type="button" class="btn btn-info" onclick="forceBgpRescan(\'' +
        sitename +
        '\')">Force BGP Rescan</button></div>',
    );
    $("#view_fe_" + sitename).append(rescanRow);
    var menCol = $(
        '<div class="nav flex-column nav-pills" id="v-pills-tab" role="tablist" aria-orientation="vertical"></div>',
    );
    var cntDiv = $('<div class="tab-content" id="v-pills-tabContent"></div>');

    for (var i = 0; i < data.length; i++) {
        if ($.isPlainObject(data[i])) {
            var row = data[i];
            var label = row["hostname"];
            if (row["updatedate"]) {
                label += " (" + new Date(row["updatedate"] * 1000).toLocaleString() + ")";
            }
            menCol.append(
                '<a class="nav-link bgp-host-link" id="v-pills-' +
                row["id"] +
                '-tab" data-idx="' +
                i +
                '" data-sitename="' +
                sitename +
                '" data-toggle="pill" href="#v-pills-' +
                row["id"] +
                '" role="tab">' +
                label +
                "</a>",
            );
            cntDiv.append(
                '<div class="tab-pane fade" id="v-pills-' + row["id"] + '" role="tabpanel"></div>',
            );
        }
    }

    var nRow = $('<div class="row">');
    menCol = $('<div class="col-3">').append(menCol);
    cntDiv = $('<div class="col-9">').append(cntDiv);
    nRow.append(menCol).append(cntDiv);
    $("#view_fe_" + sitename).append(nRow);

    $(".bgp-host-link")
        .off("click")
        .on("click", function() {
            loadBgpHost($(this).data("idx"), $(this).data("sitename"));
        });
}

function load_data() {
    var configdata = fetchConfig();
    if (!configdata) {
        return;
    }
    defineSites(configdata, false);
    var sitename = configdata["general"]["sitename"];
    $.ajax({
        url: "/api/" + sitename + "/monitoring/bgpstats?limit=100",
        dataType: "json",
        data: {},
        async: false,
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to load BGP monitoring data",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`,
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(json) {
            defineAllBgp(json, sitename);
        },
    });
}