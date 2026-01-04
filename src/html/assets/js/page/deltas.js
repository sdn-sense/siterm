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
                "Failed to load deltas",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(json) {
            tableAdd(json, ["id", "deltaid", "insertdate", "state"], saveObj);
        },
    });
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
                "Failed to load deltas",
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

function defineAllDeltas(data, sitename) {
    menCol = $(
        '<div class="nav flex-column nav-pills" id="v-pills-tab" role="tablist" aria-orientation="vertical"><\/div>',
    );
    cntDiv = $('<div class="tab-content" id="v-pills-tabContent"><\/div>');
    latest = true;
    for (var key in data["deltas"][sitename]) {
        if ($.isPlainObject(data["deltas"][sitename][key])) {
            modID = data["deltas"][sitename][key]["id"];
            tagName = modID;
            menCol.append(
                '<a class="nav-link" id="v-pills-' +
                modID +
                '-tab" data-toggle="pill" onclick="loadDelta(\'' +
                modID +
                "', '" +
                sitename +
                '\')" href="#v-pills-' +
                modID +
                '" role="tab" aria-controls="v-pills-' +
                modID +
                '" aria-selected="true">' +
                tagName +
                "<\/a>",
            );
            cntDiv.append(
                '<div class="tab-pane fade" id="v-pills-' +
                modID +
                '" role="tabpanel" aria-labelledby="v-pills-' +
                modID +
                '-tab"><\/div>',
            );
        }
    }
    nRow = $('<div class="row">');
    menCol = $('<div class="col-3">').append(menCol);
    cntDiv = $('<div class="col-9">').append(cntDiv);
    nRow.append(menCol).append(cntDiv);
    $("#view_fe_" + sitename).append(nRow);
}

function load_data() {
    var configdata = fetchConfig();
    defineSites(configdata, false);
    var sitename = configdata["general"]["sitename"];
    $.ajax({
        url: "/api/" + sitename + "/deltas?summary=true",
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
            defineAllDeltas(json, sitename);
        },
    });
}