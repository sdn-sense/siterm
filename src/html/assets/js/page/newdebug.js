SiteRMAuth.setupAjaxAuth();
$(document).ready(function() {
    load_data();
});

function collectInputs(tagName) {
    docObj = document.getElementById(tagName);
    var params = {};
    for (var i = 0; i < docObj.elements.length; i++) {
        var fieldName = docObj.elements[i].name;
        var fieldValue = docObj.elements[i].value;
        if (fieldName) {
            params[fieldName] = fieldValue;
        }
    }
    var payload = {
        hostname: params["hostname"],
        request: params,
    };

    $.ajax({
        type: "POST",
        url: "/api/" + params["sitename"] + "/debug",
        contentType: "application/json",
        data: JSON.stringify(payload),
        success: function(result) {
            newAlert(
                "New debug action submit state: " + JSON.stringify(result),
                params,
            );
        },
        error: function(jqXHR, textStatus, errorThrown) {
            newAlert(
                "Error: " +
                textStatus +
                " - " +
                errorThrown +
                " - Status: " +
                jqXHR.status +
                " - Response: " +
                jqXHR.responseText,
                params,
                "alert-danger",
            );
        },
    });
}

function doSiteUpdate(ids) {
    strSite = document.getElementById(ids + "sitename").value;
    $.ajax({
        url: "/api/" + strSite + "/hosts",
        dataType: "json",
        data: {},
        async: false,
        success: function(json) {
            for (j = 0; j < json.length; j++) {
                addDropDown(json[j]["hostname"], $("#" + ids + "hostname"));
            }
        },
    });
}

function doSiteUpdateN(ids) {
    strSite = document.getElementById(ids + "sitename").value;
    var configdata = fetchConfig();
    var sitename = configdata["general"]["sitename"];
    if (strSite === sitename) {
        const switchArray = data[sitename]["switch"];
        switchArray.forEach((name, index) => {
            addDropDown(name, $("#" + ids + "hostname"));
        });
    }
}

function doDTNUpdate(ids, ipkeys, intkeys) {
    strDTN = document.getElementById(ids + "hostname").value;
    strSite = document.getElementById(ids + "sitename").value;
    $.ajax({
        url: "/api/" + strSite + "/hosts?hostname=" + strDTN + "&details=true",
        dataType: "json",
        data: {},
        async: false,
        success: function(json) {
            for (j = 0; j < json.length; j++) {
                if (strDTN === json[j]["hostname"]) {
                    var myObject = json[j]["hostinfo"];
                    for (const [key, value] of Object.entries(
                            myObject["NetInfo"]["interfaces"],
                        )) {
                        if (!$.isEmptyObject(value["vlans"])) {
                            for (const [key1, value1] of Object.entries(
                                    value["vlans"],
                                )) {
                                for (let i = 0; i < intkeys.length; i++) {
                                    addDropDown(key1, $("#" + intkeys[i]));
                                }
                                for (const [key2, value2] of Object.entries(value1)) {
                                    console.log(key2, value2);
                                    if (
                                        typeof value2 === "object" &&
                                        value2 !== null &&
                                        key2 == 2
                                    ) {
                                        for (let i = 0; i < ipkeys.length; i++) {
                                            addDropDown(
                                                value2[0]["address"],
                                                $("#" + ipkeys[i]),
                                            );
                                        }
                                    }
                                    if (
                                        typeof value2 === "object" &&
                                        value2 !== null &&
                                        key2 == 10
                                    ) {
                                        for (let i = 0; i < ipkeys.length; i++) {
                                            addDropDown(
                                                value2[0]["address"],
                                                $("#" + ipkeys[i]),
                                            );
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
    });
}

function addDropDown(dropdownVal, saveObj) {
    saveObj.append("<option>" + dropdownVal + "<\/option>");
}

function load_data() {
    var configdata = fetchConfig();
    var sitename = configdata["general"]["sitename"];
    addDropDown(sitename, $("#f1_sitename"));
    addDropDown(sitename, $("#f2_sitename"));
    addDropDown(sitename, $("#f3_sitename"));
    addDropDown(sitename, $("#f4_sitename"));
    addDropDown(sitename, $("#f5_sitename"));
    addDropDown(sitename, $("#f6_sitename"));
    addDropDown(sitename, $("#f7_sitename"));
    addDropDown(sitename, $("#f8_sitename"));
}