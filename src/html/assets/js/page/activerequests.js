SiteRMAuth.setupAjaxAuth();
$(document).ready(function() {
    load_data();
    //setInterval(load_data, 300000);
});

function loadModel(sitename) {
    $.ajax({
        url: "/api/" + sitename + "/frontend/activedeltas",
        dataType: "json",
        data: {},
        async: false,
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to load active deltas",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(json) {
            var str = JSON.stringify(json, undefined, 4);
            model = $("<pre><\/pre>");
            model.append(syntaxHighlight(str));
            $("#v-pills-latest-" + sitename).empty();
            $("#v-pills-latest-" + sitename).append(model);
        },
    });
}

function defineAllModels(sitename) {
    menCol = $(
        '<div class="nav flex-column nav-pills" id="v-pills-tab" role="tablist" aria-orientation="vertical"><\/div>',
    );
    cntDiv = $('<div class="tab-content" id="v-pills-tabContent"><\/div>');
    modID = "latest-" + sitename;
    menCol.append(
        '<a class="nav-link" id="v-pills-' +
        modID +
        '-tab" data-toggle="pill" onclick="loadModel(\'' +
        sitename +
        '\')" href="#v-pills-' +
        modID +
        '" role="tab" aria-controls="v-pills-' +
        modID +
        '" aria-selected="true">' +
        modID +
        "<\/a>",
    );
    cntDiv.append(
        '<div class="tab-pane fade" id="v-pills-' +
        modID +
        '" role="tabpanel" aria-labelledby="v-pills-' +
        modID +
        '-tab"><\/div>',
    );
    nRow = $('<div class="row">');
    menCol = $('<div class="col-1">').append(menCol);
    cntDiv = $('<div class="col-11">').append(cntDiv);
    nRow.append(menCol).append(cntDiv);
    $("#view_fe_" + sitename).append(nRow);
}

function load_data() {
    var configdata = fetchConfig();
    var sitename = configdata["general"]["sitename"];
    defineSites(configdata, false);
    defineAllModels(sitename);
}