SiteRMAuth.setupAjaxAuth();
$(document).ready(function() {
    load_data();
    //setInterval(load_data, 300000);
});

function isString(x) {
    return Object.prototype.toString.call(x) === "[object String]";
}

function tableAddKeyLine(dataIn, dictkeys, saveObj) {
    tableTag = $('<table class="table"><\/table>');
    theadTag = $('<thead class="thead-dark"><\/thead>');
    trow = $("<tr><\/tr>");
    for (key in dictkeys) {
        trow.append('<th scope="col">' + dictkeys[key] + "<\/th>");
    }
    theadTag.append(trow);
    tableTag.append(theadTag);
    if (Array.isArray(dataIn)) {
        for (rowid in dataIn) {
            trow = $("<tr><\/tr>");
            trow.append("<td>" + rowid + "<\/td>");
            if (isString(dataIn[rowid])) {
                trow.append(
                    "<td>" +
                    dataIn[rowid].replace(new RegExp("\r?\n", "g"), "<br />") +
                    "<\/td>",
                );
            } else if (Array.isArray(dataIn[rowid])) {
                trow.append(
                    "<td>Type:" +
                    dataIn[rowid][2] +
                    "<br />" +
                    dataIn[rowid][3].replace(new RegExp("\r?\n", "g"), "<br />") +
                    "<\/td>",
                );
            }
            tableTag.append(trow);
        }
    } else if (isString(dataIn)) {
        trow = $("<tr><\/tr>");
        trow.append(
            '<td colspan="2">' +
            dataIn.replace(new RegExp("\r?\n", "g"), "<br />") +
            "<\/td>",
        );
        tableTag.append(trow);
    }

    saveObj.append(tableTag);
}

function tableAddKeyVal(dataIn, dictkeys, saveObj) {
    tableTag = $('<table class="table"><\/table>');
    theadTag = $('<thead class="thead-dark"><\/thead>');
    trow = $("<tr><\/tr>");
    for (key in dictkeys) {
        trow.append('<th scope="col">' + dictkeys[key] + "<\/th>");
    }
    theadTag.append(trow);
    tableTag.append(theadTag);
    for (key in dataIn) {
        trow = $("<tr><\/tr>");
        trow.append("<td>" + key + "<\/td>");
        trow.append("<td>" + dataIn[key] + "<\/td>");
        tableTag.append(trow);
    }
    saveObj.append(tableTag);
}

function loadDebug(debugID, sitename) {
    $.ajax({
        url: "/api/" + sitename + "/debug/" + debugID + "?details=True",
        dataType: "json",
        data: {},
        async: false,
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to load debug details",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(json) {
            json = json[0];
            model = $("<div><\/div>");
            model.append(
                '<div class="row"><b>Debug ID: <\/b>' + json["id"] + "<\/div>",
            );
            model.append(
                '<div class="row"><b>Debug Hostname: <\/b>' +
                json["hostname"] +
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
                '<div class="row"><b>Debug State: <\/b>' +
                json["state"] +
                "<\/div>",
            );
            // Debug Request
            model.append('<div class="row"><b>Debug Request:<\/b><\/div>');
            var myObject = json["requestdict"];
            tableAddKeyVal(myObject, ["Key", "Value"], model);
            // Debug Output
            if (json["output"]) {
                if (json["output"]["exitCode"]) {
                    model.append(
                        '<div class="row"><b>Runtime Exit Code: <\/b>' +
                        json["output"]["exitCode"] +
                        "<\/div>",
                    );
                }
                if (json["output"]["stderr"]) {
                    model.append('<div class="row"><b>Debug Err:<\/b><\/div>');
                    tableAddKeyLine(
                        json["output"]["stderr"],
                        ["LineNum", "Value"],
                        model,
                    );
                }
                if (json["output"]["stdout"]) {
                    model.append('<div class="row"><b>Debug Output:<\/b><\/div>');
                    tableAddKeyLine(
                        json["output"]["stdout"],
                        ["LineNum", "Value"],
                        model,
                    );
                }
                if (json["output"]["processOut"]) {
                    model.append('<div class="row"><b>Process Output:<\/b><\/div>');
                    tableAddKeyLine(
                        json["output"]["processOut"],
                        ["LineNum", "Value"],
                        model,
                    );
                }
            }
            $("#v-pills-" + debugID).empty();
            $("#v-pills-" + debugID).append(model);
        },
    });
}

function defineAllModels(data, sitename) {
    menCol = $(
        '<div class="nav flex-column nav-pills" id="v-pills-tab" role="tablist" aria-orientation="vertical"><\/div>',
    );
    cntDiv = $('<div class="tab-content" id="v-pills-tabContent"><\/div>');
    latest = true;
    for (var key in data["debug"][sitename]) {
        if ($.isPlainObject(data["debug"][sitename][key])) {
            modID = data["debug"][sitename][key]["id"];
            tagName = modID;
            menCol.append(
                '<a class="nav-link" id="v-pills-' +
                modID +
                '-tab" data-toggle="pill" onclick="loadDebug(\'' +
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
    var sitename = configdata["general"]["sitename"];
    defineSites(configdata, false);
    $.ajax({
        url: "/api/" + sitename + "/debug?limit=100",
        dataType: "json",
        data: {},
        async: false,
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to load debug details",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(json) {
            defineAllModels(json, sitename);
        },
    });
}