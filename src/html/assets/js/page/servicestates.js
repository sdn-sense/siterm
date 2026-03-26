SiteRMAuth.setupAjaxAuth();
$(document).ready(function() {
    load_data();
    //setInterval(load_data, 300000);
});

function defineAllStates(data, sitename) {
    cntDiv = $('<div class="tab-content" id="v-pills-tabContent"><\/div>');
    cntDiv.append(
        '<table class="table table-striped table-bordered table-hover" id="data-table-states"><thead class="thead-light"><tr><th>ID</th><th>Hostname</th><th>Service Name</th><th>Service State</th><th>Runtime</th><th>Version</th><th>Insert Date</th><th>Update Date</th><th>Exception</th></th><th>Refresh</th></tr></thead><tbody></tbody></table>',
    );
    nRow = $('<div class="row">');
    nRow.append(cntDiv);
    $("#view_fe_" + sitename).append(nRow);
    for (j = 0; j < data.length; j++) {
        if ($.isPlainObject(data[j])) {
            var state = data[j];
            var row = "<tr";
            if (state["servicestate"] === "OK") {
                row += ' class="table-success">';
            } else {
                row += ' class="table-danger">';
            }
            row += "<td>" + state["id"] + "</td>";
            row += "<td>" + state["hostname"] + "</td>";
            row +=
                "<td>" + state["servicename"] + "</td>";
            row +=
                "<td>" + state["servicestate"] + "</td>";
            row += "<td>" + state["runtime"] + "</td>";
            row += "<td>" + state["version"] + "</td>";
            row +=
                "<td>" +
                new Date(
                    state["insertdate"] * 1000,
                ).toLocaleString() +
                "</td>";
            row +=
                "<td>" +
                new Date(
                    state["updatedate"] * 1000,
                ).toLocaleString() +
                "</td>";
            row += "<td>" + state["exc"] + "</td>";
            // Add refresh button
            row +=
                '<td><button class="btn btn-sm btn-danger refresh-btn" ' +
                'data-hostname="' +
                state["hostname"] +
                '" ' +
                'data-servicename="' +
                state["servicename"] +
                '" ' +
                'data-sitename="' +
                sitename +
                '">' +
                "Refresh</button></td>";

            row += "</tr>";
            $("#data-table-states tbody").append(row);
        }
    }

    // Attach refresh button to an event handler
    $(".refresh-btn")
        .off("click")
        .on("click", function() {
            var hostname = $(this).data("hostname");
            var servicename = $(this).data("servicename");
            var sitename = $(this).data("sitename");

            $.ajax({
                url: "/api/" + sitename + "/servicestates" +
                    "?hostname=" + encodeURIComponent(hostname) +
                    "&servicename=" + encodeURIComponent(servicename),
                type: "DELETE",
                contentType: "application/json",
                success: function(res) {
                    alert("Deleted: " + hostname + " / " + servicename);
                    $(this).closest("tr").remove();
                }.bind(this),
                error: function(xhr, status, error) {
                    showAjaxWarning(
                        "Failed to delete service state",
                        `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
                    );
                    console.error("AJAX error:", status, xhr.responseText);
                },
            });
        });
}

function load_data() {
    var configdata = fetchConfig();
    var sitename = configdata["general"]["sitename"];
    defineSites(configdata, false);
    $.ajax({
        url: "/api/" + sitename + "/servicestates",
        dataType: "json",
        data: {},
        async: false,
        success: function(json) {
            defineAllStates(json, sitename);
        },
        error: function(xhr, status, error) {
            showAjaxWarning("Failed to load service states",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`);
                console.error("AJAX error:", status, xhr.responseText);
        },
    });
}