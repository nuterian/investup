var https       		= require('https');
var profileFeatures     = require('./profileFeatures');
var ml                  = require('machine_learning');
var fs                  = require('fs');

var API_KEY = "26bb2c820b0842a99cba19563c196506";

function getOrganizationData(permalink, callback) {
	var url = 'https://api.crunchbase.com/v/3/organizations/' + permalink + '?user_key=' + API_KEY;
	var statusCode = -1;
	https.get(url, function(res) {
		statusCode = res.statusCode;
	    res.setEncoding('utf8');
	    var data = '';

	    res.on('data', function (chunk) {
	        data += chunk;
	    });

	    res.on('end', function(){
	        callback(data, statusCode);
	    });
	}).on('error', function(e) {
		callback('', statusCode);
	});
}

function getKeywordMatchScore(a, keys) {
    var score = 0;

    a = a.toLowerCase();
    a = a.replace(/\W+/g, ' '); //Convert all non-word characters to spaces.
    _a = a.split(' ');

    keys.forEach(function(k, i) {
        _a.forEach(function(b, j){
            if( b == k ) {
                score += 10;
                if(i == j) {
                    score += 3;
                }
                else {
                    score -= 1;
                }
            }
            else if(b.indexOf(k) > -1) {
                score += 3;
                if(i == j) {
                    score += 2;
                }
            }
            else {
                score -= 1;//Math.abs(b.length - k.length);
            }
        });
    });

    var diff = Math.abs(_a.length - keys.length);
    score -= diff;

    return score;
}

function getOrganizationProfileFromData(data) {
	if(!data || data === '') {
		return null;
	}

	var ret = {};
	for(var feature in profileFeatures.profileFeatures) {
		ret[feature] = profileFeatures.profileFeatures[feature](data.data);
	}

	return ret;
}

function getCategoriesFromData(data) {
    data = data.data;
    if(data.relationships.categories) {
        var res = [];
        data.relationships.categories.items.forEach(function(cat) {
            res.push(cat.properties.name);
        });
        return res;
    }
    return [];
}

function getPredictionInput(meta, data) {
    var train = [];
    profileFeatures.trainingFeatures.forEach(function(f){
        train.push(profileFeatures.profileFeatures[f](data.data));
    });
    train.push(meta.s);
    return train;
}

function getPrediction(input, tree) {
    var dt = new ml.DecisionTree({
        data: [],
        result: []
    });
    dt.tree = tree;
    return dt.classify(input);
}

function readTree(category) {
    return JSON.parse(fs.readFileSync('./data/trees/' + category + '.json'));
}

module.exports = {
	getOrganizationData: getOrganizationData,
	getKeywordMatchScore: getKeywordMatchScore,
	getOrganizationProfileFromData: getOrganizationProfileFromData,
    getCategoriesFromData: getCategoriesFromData,
    getPredictionInput: getPredictionInput,
    getPrediction: getPrediction,
    readTree: readTree
}