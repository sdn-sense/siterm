SiteRMAuth.setupAjaxAuth();
$(document).ready(function() {
    load_data();
});

function tableAdd(dataIn, dictkeys, saveObj) {
    tableTag = $('<table class="table"><\/table>');
    theadTag = $('<thead class="thead-dark"><\/thead>');
    trow = $("<tr><\/tr>");
    for (key in dictkeys) {
        trow.append('<th scope="col">' + dictkeys[key] + "<\/th>");
    }
    theadTag.append(trow);
    tableTag.append(theadTag);
    for (rowid in dataIn) {
        trow = $("<tr><\/tr>");
        for (key in dictkeys) {
            if (dictkeys[key] === "insertdate") {
                var date = new Date(dataIn[rowid][dictkeys[key]] * 1000);
                trow.append(
                    "<td>" +
                    date.getDate() +
                    "/" +
                    (date.getMonth() + 1) +
                    "/" +
                    date.getFullYear() +
                    " " +
                    date.getHours() +
                    ":" +
                    date.getMinutes() +
                    ":" +
                    date.getSeconds() +
                    "<\/td>",
                );
            } else {
                trow.append("<td>" + dataIn[rowid][dictkeys[key]] + "<\/td>");
            }
        }
        tableTag.append(trow);
    }
    saveObj.append(tableTag);
}

function deltaStates(deltaID, sitename, saveObj) {
    $.ajax({
        url: "/api/" + sitename + "/deltas/" + deltaID + "/timestates?limit=100",
        dataType: "json",
        data: {},
        async: false,
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to load delta timestates",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(json) {
            tableAdd(json, ["id", "deltaid", "insertdate", "state"], saveObj);
        },
    });
}

function appendInfoRow(saveObj, label, value) {
    const row = $('<div class="row"></div>');
    row.append($("<b></b>").text(label + ": "));
    row.append(document.createTextNode(value || ""));
    saveObj.append(row);
}

function appendDeltaRequestInfo(requestData, saveObj) {
    const requestInfo = requestData["requestInfo"] || {};
    const requestor = requestInfo["fullname"] || requestInfo["email"] || requestInfo["username"] || "Not recorded";

    saveObj.append('<div class="row"><b>Request Information:<\/b><\/div>');
    saveObj.append('<div class="row">============================================<\/div>');
    appendInfoRow(saveObj, "Requestor", requestor);
    appendInfoRow(saveObj, "Email", requestInfo["email"]);
    appendInfoRow(saveObj, "Organization", requestInfo["organization"]);
    appendInfoRow(saveObj, "Request Host", requestInfo["host"]);
    appendInfoRow(saveObj, "Recorded User", requestInfo["username"]);
}

function loadDeltaRequestInfo(deltaID, sitename, saveObj) {
    $.ajax({
        url: "/api/" + sitename + "/deltas/" + deltaID + "/requestinfo",
        dataType: "json",
        data: {},
        async: false,
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to load delta request information",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
            appendDeltaRequestInfo({}, saveObj);
        },
        success: function(json) {
            appendDeltaRequestInfo(json, saveObj);
        },
    });
}

function deltaErrorText(rawError) {
    // Stored as JSON {errType, errNo, errMsg}; older rows may hold plain text.
    if (!rawError) {
        return "";
    }
    let err;
    try {
        err = JSON.parse(rawError);
    } catch (e) {
        return String(rawError);
    }
    if (!$.isPlainObject(err)) {
        return String(rawError);
    }
    const errMsg = typeof err["errMsg"] === "string" ? err["errMsg"] : JSON.stringify(err["errMsg"]);
    const errType = String(err["errType"] || "Unknown").replace(/^<class '(.*)'>$/, "$1");
    return `${errMsg}\n(Type: ${errType}, Code: ${err["errNo"]})`;
}

function appendDeltaError(rawError, saveObj) {
    const errText = deltaErrorText(rawError);
    if (!errText) {
        return;
    }
    saveObj.append(
        $('<div class="row alert alert-danger"></div>')
        .append($("<b></b>").text("Delta Error: "))
        .append($('<span style="white-space: pre-wrap;"></span>').text(errText))
    );
}

function forceCommit(deltaID, sitename) {
    $.ajax({
        url: "/api/" + sitename + "/deltas/" + deltaID + "/actions/forcecommit",
        type: "PUT",
        dataType: "json",
        data: {},
        success: function(json) {
            alert("Force Commit Done for Delta ID: " + deltaID);
        },
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to force commit delta",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
    });
}

function loadDelta(deltaID, sitename) {
    $.ajax({
        url: "/api/" + sitename + "/deltas/" + deltaID + "?summary=false",
        dataType: "json",
        data: {},
        async: false,
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to load deltas",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(json) {
            if (!json || !json.length) {
                showAjaxWarning(
                    "Failed to load deltas",
                    "No data returned for delta " + deltaID
                );
                return;
            }
            json = json[0];
            model = $("<div><\/div>");
            model.append(
                '<div class="row"><b>Delta UID: <\/b>' + json["id"] + "<\/div>",
            );
            model.append(
                '<div class="row"><b>Delta State: <\/b>' +
                json["state"] +
                "<\/div>",
            );
            appendDeltaError(json["error"], model);
            model.append(
                '<div class="row"><b>Insert Date: <\/b>' +
                json["insertdate"] +
                "<\/div>",
            );
            model.append(
                '<div class="row"><b>Update Date: <\/b>' +
                json["updatedate"] +
                "<\/div>",
            );
            model.append(
                '<div class="row"><b>Delta Type: <\/b>' +
                json["deltat"] +
                "<\/div>",
            );
            model.append(
                '<div class="row"><b>Delta ModAdd: <\/b>' +
                json["modadd"] +
                "<\/div>",
            );
            model.append(
                '<div class="row"><b>Delta ModelID: <\/b>' +
                json["modelid"] +
                "<\/div>",
            );
            loadDeltaRequestInfo(deltaID, sitename, model);
            // Delta Info From Orchestrator
            model.append(
                '<div class="row"><b>Full Delta Information From Orhestrator:<\/b><\/div>',
            );
            model.append(
                '<div class="row">============================================<\/div>',
            );
            model.append(
                '<div class="row"><b>    Model Addition: <\/b><\/div>',
            );
            mrmlSaver(json["addition"], model);
            model.append(
                '<div class="row"><b>    Model Reduction: <\/b><\/div>',
            );
            mrmlSaver(json["reduction"], model);
            model.append('<div class="row"><b>DELTA STATES:<\/b><\/div>');
            model.append(
                '<div class="row">============================================<\/div>',
            );
            deltaStates(deltaID, sitename, model);
            $("#v-pills-" + deltaID).empty();
            $("#v-pills-" + deltaID).append(model);
            // Add button which will call PUT /api/<sitename>/deltas/<deltaid>/actions/forcecommit
            model.append(
                '<div class="row"><button type="button" class="btn btn-primary" onclick="forceCommit(\'' +
                deltaID +
                "', '" +
                sitename +
                "')\">Force Commit<\/button><\/div>",
            );
        },
    });
}

const DELTAS_PAGE_SIZE = 50;

const DELTA_STATE_BADGES = {
    activated: "badge-success",
    accepted: "badge-info",
    failed: "badge-danger",
};

function defineAllDeltas(data, sitename) {
    let menCol = $(
        '<div class="nav flex-column nav-pills" role="tablist"></div>'
    );
    let cntDiv = $('<div class="tab-content"></div>');

    for (let i = 0; i < data.length; i++) {
        const delta = data[i];

        if ($.isPlainObject(delta)) {
            const modID = delta["id"];
            const badge = DELTA_STATE_BADGES[delta["state"]] || "badge-secondary";

            menCol.append(
                $('<a class="nav-link" data-toggle="pill" role="tab"></a>')
                .attr("id", "v-pills-" + modID + "-tab")
                .attr("href", "#v-pills-" + modID)
                .on("click", () => loadDelta(modID, sitename))
                .text(modID)
                .append($('<span class="badge ml-2"></span>').addClass(badge).text(delta["state"]))
            );

            cntDiv.append(
                $('<div class="tab-pane fade" role="tabpanel"></div>').attr("id", "v-pills-" + modID)
            );
        }
    }

    const nRow = $('<div class="row">')
        .append($('<div class="col-3">').append(menCol))
        .append($('<div class="col-9">').append(cntDiv));

    $("#deltas_list_" + sitename).empty().append(nRow);
}

function loadDeltasPage(sitename, offset) {
    $.ajax({
        url: "/api/" + sitename + "/deltas",
        dataType: "json",
        data: {
            summary: true,
            limit: DELTAS_PAGE_SIZE,
            offset: offset
        },
        error: function(xhr, status, error) {
            if (xhr.status === 404) {
                $("#deltas_list_" + sitename).empty().append($('<div class="alert alert-info"></div>').text("No deltas found."));
                $("#deltas_pager_top_" + sitename + ", #deltas_pager_bottom_" + sitename).empty();
                return;
            }
            showAjaxWarning(
                "Failed to load deltas",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(json, status, xhr) {
            const total = totalCountHeader(xhr);
            const onPage = (newOffset) => loadDeltasPage(sitename, newOffset);
            defineAllDeltas(json, sitename);
            $("#deltas_pager_top_" + sitename).empty().append(paginationNav(offset, DELTAS_PAGE_SIZE, json.length, total, onPage));
            $("#deltas_pager_bottom_" + sitename).empty().append(paginationNav(offset, DELTAS_PAGE_SIZE, json.length, total, onPage));
        },
    });
}

function load_data() {
    var configdata = fetchConfig();
    if (!configdata) {
        return;
    }
    defineSites(configdata, false);
    var sitename = configdata["general"]["sitename"];
    $("#view_fe_" + sitename).append(
        $("<div></div>").attr("id", "deltas_pager_top_" + sitename),
        $("<div></div>").attr("id", "deltas_list_" + sitename),
        $("<div></div>").attr("id", "deltas_pager_bottom_" + sitename),
    );
    loadDeltasPage(sitename, 0);
}