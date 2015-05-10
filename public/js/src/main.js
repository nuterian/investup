function numberWithCommas(x) {
    return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

var CompanyThumbnail = React.createClass({
	getInitialState: function() {
		return {
			status: 'loading'
		};
	},

	getDefaultProps: function(){
		return {
			alignTop: false
		}
	},

	componentWillMount: function(){
		if(!this.props.src) {
			this.handleError();
		}
	},

	componentWillReceiveProps: function(nextProps) {
		if(nextProps.src !== this.props.src) {
			var imgNode = this.refs.img.getDOMNode();
			imgNode.style.width = this.props.maxSize + 'px';
			imgNode.style.height = this.props.maxSize + 'px';
			imgNode.style.marginTop = null;
			imgNode.style.marginLeft = null;
			this.setState({
				status: 'loading'
			});			
		}
	},	

	handleLoad: function(){
		var imgNode = this.refs.img.getDOMNode();
		var imgWidth = imgNode.width || this.props.maxSize;
		var imgHeight = imgNode.height || this.props.maxSize;
		if(imgNode.width > imgNode.height) {
			imgNode.style.width = this.props.maxSize + 'px';
			imgNode.style.height = 'auto';
			imgNode.style.marginTop = ( this.props.maxSize / 2 - (this.props.maxSize * imgNode.height / imgNode.width ) / 2 ) + 'px';	
		}
		else {
			imgNode.style.height = this.props.maxSize + 'px';
			imgNode.style.width = 'auto';
			imgNode.style.marginLeft = ( this.props.maxSize / 2 - (this.props.maxSize * imgNode.width / imgNode.height ) / 2 ) + 'px';
		}
		this.setState({
			status: 'loaded'
		});
	},

	handleError: function(){
		this.setState({
			status: 'failed'
		});
	},

	render: function() {
	    var className = 'thumb thumb-' + this.state.status;
	    return (
	    	<div className={className}>
	    		<div className="thumb-placeholder" style={{fontSize: this.props.maxSize/2.1 + 'px', lineHeight: this.props.maxSize + 'px'}}>{this.props.alt ? this.props.alt[0] : String.fromCharCode(65 + Math.random() * 25) }</div>
		    	<div className="spinner" style={{width: this.props.maxSize + 'px', height: this.props.maxSize + 'px'}}></div>
		      	<img src={this.props.src} onLoad={this.handleLoad} onError={this.handleError} ref="img"/>
		     </div>
	    );
	}
});

var CompanyRow = React.createClass({
    render: function() {
    	var maxThumbSize = 40;
        return (
            <li className="company-list-item row">
            	<div className="company-item-img col">
            		<CompanyThumbnail src={this.props.company.i} maxSize={maxThumbSize} alt={this.props.company.n} />
            	</div>
            	<div className="company-name col"><a href={'#' + this.props.company.p}>{this.props.company.n}</a></div>
            </li>
        );
    }
});

function pager(page) {
	if(page.numPages < 2) 
		return;

	var pageLinks = [];
	if(page.currentPage > 1) {
		pageLinks.push(<a className="page-link col" onClick={page.handleClick(page.currentPage - 1)}>‹</a>)
	}

	var startPage = page.currentPage - (page.currentPage > 1 ? 6 : 7);
	var endPage = page.currentPage + 6;
	if(startPage <= 0) {
	    endPage -= (startPage - 1);
	    startPage = 1;
	}
	if (endPage > page.numPages) {
    	endPage = page.numPages;
	}

	for(var i = startPage; i <= endPage; i++) {
		if(page.currentPage == i) {
			pageLinks.push(<a className="page-link page-curr col">{i}</a>)	
		}
		else {
			pageLinks.push(<a className="page-link col" onClick={page.handleClick(i)}>{i}</a>)
		}		
	}

	if (page.currentPage < page.numPages) {
		pageLinks.push(<span className="page-link col-right" onClick={page.handleClick(page.currentPage + 1)}>›</span>)
	}
	return <div className="pager row">{pageLinks}</div>
}

var SearchResultRelatedList = React.createClass({
	getDefaultProps: function(){
		return {
			companies: []
		};
	},

	render: function(){
		var rows = [];
		this.props.companies.forEach(function(company) {
			rows.push(
				<li className="row">
					<div className="col company-item-img"><CompanyThumbnail maxSize="30" src={company.i} /></div>
					<div className="col" className="company-name"><a href={'#' + company.p}>{company.n}</a></div>
				</li>
			);
		});

		return (
			<div>
				<h3 className="light">{'Related'}</h3>
				<ul className="company-list">
					{rows}
				</ul>
			</div>
		);
	}
});

var SearchResultList = React.createClass({
	getInitialState: function() {
		return {
			companies: [],
			related: [],
			currentPage: null,
			status: 'noquery',
		}
	},

	getDefaultProps: function() {
		return {
			pageSize: 10
		}
	},

	loadCompaniesFromServer: function(q) {
		this.setState({status: 'loading', currentPage: null});
		var queryUrl =  this.props.url + encodeURIComponent(q);
	    $.ajax({
	      	url: queryUrl,
	      	dataType: 'json',
	      	success: function(data) {
	        	this.setState({companies: data, currentPage: 1, status: 'loaded'});
	      	}.bind(this),
	      	error: function(xhr, status, err) {
	      		this.setState({companies: [], currentPage: 1, status: 'failed'});
	        	console.error(queryUrl, status, err.toString());
	      	}.bind(this)
	    });		
	},

	loadRelatedFromServer: function() {
		this.setState({related: []});
		var data = this.getPage().companies;
	    $.ajax({
	      	url: '/related',
	      	type: 'POST',
	      	dataType: 'json',
	      	data: JSON.stringify(data.map(function(c){ return c.p; })),
	      	contentType: 'application/json',
	      	success: function(data) {
	        	this.setState({related: data});
	      	}.bind(this),
	      	error: function(xhr, status, err) {
	      		this.setState({related: []});
	        	console.error('/related', status, err.toString());
	      	}.bind(this)
	    });		
	},

	componentWillMount: function() {
		if(this.props.query.length >= 3) {
			this.loadCompaniesFromServer(this.props.query);
		}
	},
	
	componentWillReceiveProps: function(nextProps) {
		if(this.props.query !== nextProps.query) {
			if(nextProps.query.length < 3) {
				this.setState({companies:[], status: 'noquery'});
			}
			else {
				this.loadCompaniesFromServer(nextProps.query);	
			}
		}
  	},

	getPage: function() {
	   	var start = this.props.pageSize * ((this.state.currentPage || 1) - 1);
	    var end = start + this.props.pageSize;
	    return {
	      	currentPage: this.state.currentPage || 1, 
	      	companies: this.state.companies.slice(start, end), 
	      	numPages: this.getNumPages(), 
	      	handleClick: function(pageNum) {
	        	return function() { 
	        		this.handlePageChange(pageNum);
	        	}.bind(this)
	      	}.bind(this)
	    }
	},

	getNumPages: function() {
	    var numPages = Math.floor(this.state.companies.length / this.props.pageSize);
	    if (this.state.companies.length % this.props.pageSize > 0) {
	      	numPages++
	    }
	    return numPages;
	},

	handlePageChange: function(pageNum) {
	    this.setState({currentPage: pageNum});
	},

	componentDidUpdate: function(nextProps, nextState) {
		if(this.state.currentPage !== nextState.currentPage) {
			this.loadRelatedFromServer();
		}
	},

    render: function() {
    	var page = this.getPage();
        var rows = page.companies.map(function(company) {
        	return <CompanyRow company={company} />
        });

        var resultStatus;
        switch(this.state.status){
        	case 'noquery':
        		resultStatus = 'Type a query (atleast 3 characters)';
        		break;
        	case 'loading':
        		resultStatus = 'Searching...';
        		break;
        	case 'loaded':
        		if(this.state.companies.length > 0) {
        			resultStatus = numberWithCommas(this.state.companies.length) + ' results';
        		}
        		else {
        			resultStatus = 'Your query "' + this.props.query + '" returned no results'
        		}
        }

        return (
        	<div>
        		<div className="row">
		        	<div className="list-wrapper col">
		        		<div className="result-status">{resultStatus}</div>
			        	<ul className="company-list">
			        		{rows}
			        	</ul>
				    </div>
			        <div className="related-list col-right">
			        {this.state.related.length > 0 ?
		        		<SearchResultRelatedList companies={this.state.related} />
		        		: null
			        }
			        </div>
		        </div>
	        	{pager(page)}
        	</div>
        );
    }
});

var SearchBar = React.createClass({
	handleKeyDown: function() {
		var query = React.findDOMNode(this.refs.search).value.trim();
		this.props.onQuery(query);
	},

    componentWillMount: function() {
    	this.handleKeyDown = _.debounce(this.handleKeyDown, 300);
    },

    componentWillReceiveProps: function(nextprops) {
    	if(	nextprops.query !== this.props.query) {
    		React.findDOMNode(this.refs.search).value = nextprops.query;
    	}
    },

    render: function() {
        return (
            <input type="text" placeholder="Search by company name..." className="sb" onKeyDown={this.handleKeyDown} ref="search" />
        );
    }
});

var BounceSpinner = React.createClass({
	render: function(){
		return (
			<div className="spinner-bounce">
			  	<div className="bounce1"></div>
			  	<div className="bounce2"></div>
			  	<div className="bounce3"></div>
			</div>
		);
	}
});

function getMinPow10(x) {
	var pow = 0;
	while(Math.floor(x/=10)) {
		pow++;
	}
	return pow;
}


function generateFundingGraph(el, data, width, height) {
	var margin = {top: 30, right: 20, bottom: 30, left: 60},
	    width = width - margin.left - margin.right,
	    height = height - margin.top - margin.bottom;

	// Parse the date / time
	var parseDate = d3.time.format("%Y-%m-%d").parse;

	// Set the ranges
	var x = d3.time.scale().range([0, width]);
	var y = d3.scale.linear().range([height, 0]);

	// Define the axes
	var xAxis = d3.svg.axis().scale(x)
	    .orient("bottom").ticks(5);

	var yAxis = d3.svg.axis().scale(y)
	    .orient("left").ticks(5);

	// Define the line
	var line = d3.svg.line()
	    .x(function(d) { return x(d.d); })
	    .y(function(d) { return y(d.a); });
	    
	// Adds the svg canvas
	var svg = d3.select(el).html('')
	    .append("svg")
	        .attr("width", width + margin.left + margin.right)
	        .attr("height", height + margin.top + margin.bottom)
	    .append("g")
	        .attr("transform", 
	              "translate(" + margin.left + "," + margin.top + ")");


	var sumAmmounts = {};
	var foundedDate = parseDate(data.founded_on);
	var minDate = foundedDate || Number.POSITIVE_INFINITY, minAmount = Number.POSITIVE_INFINITY;
	var fundingRounds =  data.funding_rounds;
	fundingRounds.forEach(function(round) {
		var roundDate = parseDate(round.d);
		if(roundDate < minDate) {
			minDate = roundDate;
		}

		if(!(roundDate.getUTCFullYear() in sumAmmounts)){
			sumAmmounts[roundDate.getUTCFullYear()] = 0;
		}
		sumAmmounts[roundDate.getUTCFullYear()] += round.a;
	});

	
	for(var year in sumAmmounts) {
		if(sumAmmounts[year] < minAmount) {
			minAmount = sumAmmounts[year];
		}
	}
	var minAmountPow10 = getMinPow10(minAmount);
	minAmountPow10 = Math.pow(10, minAmountPow10 - 2);

	var inputData = [], maxDate = Number.NEGATIVE_INFINITY;
	parseDate = d3.time.format("%Y").parse;
	for(var year in sumAmmounts) {
		var date = parseDate(year);
		if(date > maxDate) {
			maxDate = date;
		}
		inputData.push({d: date, a: sumAmmounts[year] / minAmountPow10})
	}
	inputData.sort(function(a, b) {
		return a.d - b.d;
	});
    if(minDate < inputData[0].d) {
    	inputData.unshift({d: minDate, a: 0});	
    	minAmount = 0;
    }
    else {
    	minDate = inputData[0].d;
    }

    //console.log(new Date(minDate.getUTCFullYear() - 1, 0), inputData[0].d, Math.min(parseDate(maxDate.getUTCFullYear() + 4 + ''), new Date()));
    x.domain([new Date(minDate.getUTCFullYear() - 1, 0), Math.min(parseDate(maxDate.getUTCFullYear() + 4 + ''), new Date())]);
    y.domain([minAmount/minAmountPow10, d3.max(inputData, function(d) { return d.a; })]);

    svg.append("g").attr("class", "x axis").attr("transform", "translate(0," + height + ")").call(xAxis);
    svg.append("g").attr("class", "y axis").call(yAxis);

    svg.append("path").attr("class", "line").attr("d", line(inputData));

    svg.selectAll(".dot")
	  	.data(inputData).enter()
	  	.append("circle").attr('cx', function(d) { return x(d.d); }).attr('cy', function(d) { return y(d.a); }).attr('r', 3).attr('fill', '#16a085');

	if(foundedDate){
		console.log('founded');
		svg.append('circle').attr('cx', x(foundedDate)).attr('cy', y(minAmount/minAmountPow10) ).attr('r', 4).attr('fill', '#f1c40f');		
	}

}

var CompanyProfileSummary = React.createClass({
	statuses: {
		LOADING: 'loading',
		LOADED: 'loaded',
		FAILED: 'failed'
	},

	getInitialState: function() {
		return {
			status: this.statuses.LOADING,
		}
	},

	getDefaultProps: function() {
		return {
			profile: null
		}
	},

	componentWillReceiveProps: function(nextProps) {
		if(nextProps.profile == null ){
			this.setState({status: this.statuses.LOADING});
		}
		else if(!_.isEqual(this.props.profile, nextProps.profile)) {
			this.setState({status: this.statuses.LOADED})
		}
	},

	render: function() {
		var numEmployees = null;
		if(this.props.profile) {
			var availableProps = [];
			if(this.props.profile.homepage_url) {
				availableProps.push({l: "Website", t: "a", a: {href: this.props.profile.homepage_url}, v: (new URL(this.props.profile.homepage_url).hostname) });
			}

			if(this.props.profile.founded_on) {
				availableProps.push({l: "Founded", t: "div", v: this.props.profile.founded_on.split('-')[0] });
			}

			if(this.props.profile.age) {
				availableProps.push({l: "Exit age (months)", t: "div", v: this.props.profile.age });
			}

			if(this.props.profile.location) {
				availableProps.push({l: "Location", t: "div", v: this.props.profile.location.c + ', ' + this.props.profile.location.r });
			}

			var propWidth = 100/availableProps.length + '%';
			var profileProps = [];
			availableProps.forEach(function(p) {
				profileProps.push(
					React.createElement("div", {className: "col", style: {width: propWidth}}, 
						React.createElement("div", {className: "profile-label"}, p.l), 
						React.createElement(p.t, p.a || null, p.v)
					)
				);
			});

			if(this.props.profile.num_employees) {
				var split = this.props.profile.num_employees.split('-');
				if(split.length > 1) {
					numEmployees = numberWithCommas(split[0]) + ' - ' + numberWithCommas(split[1]);
				}
				else {
					numEmployees = numberWithCommas(split[0]);
				}
			}

		}

		var scoreClass = getSuccessClass(this.props.profile);
		return (
			<div className={"profile-summary " + this.state.status}>
				{ this.props.profile ?
					<div className={"profile-summary-content " + scoreClass.s}>
						<div className="profile-panel row">
							<div className="col">
								<div className="profile-label">{"Success score"}</div>
								<div className="profile-success-bar">
									<div className="profile-success-fill"></div>
									<div className="profile-success-score">{Math.round(this.props.profile.success.all * 2250) || <span className="light">{"n/a"}</span>}</div>
								</div>
							</div>
							
							{ !this.props.profile.total_funding || this.props.profile.total_funding == 0 ?
								this.props.profile.total_funding_investments == 0 ?
									<div className="col">
										<div className="profile-label">{"Total funding"}</div>
										<div className="light">{"n/a"}</div>
									</div>
									:
									<div className="col">
										<div className="profile-label">{"Total investments"}</div>
										<div>{numeral(this.props.profile.total_funding_investments).format('($ 0.00a)')}</div>
									</div>
								:
								<div className="col">
									<div className="profile-label">{"Total funding"}</div>
									<div>{numeral(this.props.profile.total_funding).format('($ 0.00a)')}</div>
								</div>
							}
							<div className="col">
								<div className="profile-label">{"Employees"}</div>
								<div>{numEmployees || <span className="light">{"unknown"}</span>}</div>
							</div>
						</div>
						<div className="profile-props row">{profileProps}</div>
					</div> 
					: null
				}
				<BounceSpinner />
			</div>
		);
	}
});

var CompanyCondensedRow = React.createClass({
	render: function(){
		var maxThumbSize = 36;
		return (
            <li className="company-list-item row">
            	<div className="company-item-img col">
            		<CompanyThumbnail src={this.props.company.i} maxSize={maxThumbSize} alt={this.props.company.n} />
            	</div>
            	<div className="company-name col"><a href={'#' + this.props.company.p}>{this.props.company.n}</a></div>
            </li>
		);
	}
})

var CompanyCondensedListing = React.createClass({
	getDefaultProps: function(){
		return {
			companies: []
		}
	},

	render: function() {
		var companies = this.props.companies;
		var rows = [];
		for(var i = 0; i < Math.min(4, companies.length); i++) {
			rows.push(<CompanyCondensedRow company={companies[i]} />);
		}
        return (
        	<ul className="company-list company-list-condensed">
        		{rows}
        	</ul>
        );
	}
});


var CompanyCompetitors = React.createClass({
	getInitialState: function() {
		return {
			competitors: { c: [] }
		}
	},

	getDefaultProps: function(){
		return {
			permalink: null,
			url: '/competitors?p='
		}
	},

	loadCompetitorsFromServer: function(p) {
		var queryUrl = this.props.url + p;
	    $.ajax({
	      	url: queryUrl,
	      	dataType: 'json',
	      	success: function(data) {
	        	this.setState({competitors: data});
	      	}.bind(this),
	      	error: function(xhr, status, err) {
	        	console.error(queryUrl, status, err.toString());
	      	}.bind(this)
	    });	
	},

	componentWillMount: function(){
		if(this.props.permalink) {
			this.setState({competitors: { c: [] }});
			this.loadCompetitorsFromServer(this.props.permalink);
		}
	},

	componentWillReceiveProps: function(nextProps){
		console.log(nextProps);
		if(this.props.permalink !== nextProps.permalink) {
			this.setState({competitors: { c: [] }});
			this.loadCompetitorsFromServer(this.props.permalink);
		}
	},

	render: function(){
		//console.log('COMPET: ', this.props, this.state.competitors.c);
		return (
			<div>
				{ this.state.competitors.c.length > 0 ?
				<div className="profile-section">
					<div className="row section-title">
						<h3 className="col">{'Competitors'}</h3>
						<div className="col-right profile-label">{'Rank  '}<span className="emph">{this.state.competitors.r}</span>{'/' + this.state.competitors.t}</div>
					</div>
					<CompanyCondensedListing companies={this.state.competitors.c} />
				</div>
				: null
				}
			</div>
		);
	}
});

function getSuccessClass(profile) {
	if(!profile) return null;
	var score = profile.success.all;
	var stdDivider = 3;
	if(profile.is_acquired || profile.num_acquisitions > 0) {
		if(score < 0.1) {
			return {s: 'bad' };
		}
		else if(score >= 0.1 && score < 0.5) {
			return {s: 'ok' };
		}
		else if(score >= 0.5 && score < 0.75) {
			return {s: 'good'};
		}
		else if(score >= 0.75 && score < 0.85) {
			return {s: 'great'};
		}
		else {
			return {s: 'awesome'};
		}
	}
	else {
		console.log(profile, profile.is_acquired);
		if(profile.age < 42) {
			if(score < 0.15) {
				if(profile.rate < -stdDivider) return {s: 'ok', c: 'incubated'};
				else if(profile.rate >= -stdDivider && profile.rate < stdDivider) return {s: 'rising'};
				else return {s: 'hot'};
			}
			else {
				if(profile.rate < -stdDivider) return {s: 'rising', c: 'needs-funding'};
				else if(profile.rate >= -stdDivider && profile.rate < stdDivider) return {s: 'hot'};
				else return {s: 'very-hot'};			
			}
		}
		else {
			if(score < 0.15) {
				if(profile.rate < -stdDivider) return {s: 'ok'};
				else if(profile.rate >= -stdDivider && profile.rate < stdDivider) return {s: 'ok'};
				else return {s: 'rising'};
			}
			else if(score >= 0.15 && score < 0.5) {
				if(profile.rate < -stdDivider) return {s: 'ok'};
				else if(profile.rate >= -stdDivider && profile.rate < stdDivider) return {s: 'rising'};
				else return {s: 'hot'};			
			}
			else {
				if(profile.rate < -stdDivider) return {s: 'rising'};
					else if(profile.rate >= -stdDivider && profile.rate < stdDivider) return {s: 'hot'};
					else return {s: 'very-hot'};					
			}	
		}
	}
}

var CompanyProfile = React.createClass({
	getInitialState: function(){
		return {
			profile: null,
			meta: null,
			status: "loading"			
		}
	},

	getDefaultProps: function() {
		return {
			profileUrl: "/profile?p=",
			metaUrl: "/meta?p="
		}
	},

	loadProfileFromServer: function(p) {
		var queryUrl =  this.props.profileUrl + p;
	    $.ajax({
	      	url: queryUrl,
	      	dataType: 'json',
	      	success: function(data) {
	        	this.setState({profile: data, status: "loaded"});
	      	}.bind(this),
	      	error: function(xhr, status, err) {
	        	console.error(queryUrl, status, err.toString());
	      	}.bind(this)
	    });		
	},

	loadMetaFromServer: function(p) {
		var queryUrl =  this.props.metaUrl + p;
	    $.ajax({
	      	url: queryUrl,
	      	dataType: 'json',
	      	success: function(data) {
	        	this.setState({meta: data});
	      	}.bind(this),
	      	error: function(xhr, status, err) {
	        	console.error(queryUrl, status, err.toString());
	      	}.bind(this)
	    });
	},

	componentWillMount: function() {
		this.setState({status: "loading", profile: null});
		this.loadMetaFromServer(this.props.permalink);
		this.loadProfileFromServer(this.props.permalink);
	},

	componentWillReceiveProps: function(nextprops) {
		if(this.props.permalink !== nextprops.permalink) {
			this.setState({status: "loading", profile: null});
			this.loadMetaFromServer(nextprops.permalink);
			this.loadProfileFromServer(nextprops.permalink);
		}
	},

	componentDidUpdate: function(){
		if(this.state.profile && this.state.profile.funding_rounds.length > 0){
			generateFundingGraph(this.refs.fundingGraph.getDOMNode(), this.state.profile, 500, 276);
		}
	},

	render: function(){
		var successClass = getSuccessClass(this.state.profile);
		var tags = [];
		if(this.state.profile) {
			if(this.state.profile.is_acquired) {
				tags.push(<div className="col tag tag-gray">{'Acquired'}</div>);	
			}
			else if(this.state.profile.num_acquisitions === 0 && successClass) {
				tags.push(<div className={"col tag " + successClass.s}>{successClass.s.split('-').join(' ')}</div>);
			}
			else if(successClass.c) {
				tags.push(<div className={"col tag " + successClass.c}>{successClass.c.split('-').join(' ')}</div>);	
			}
		}
		return (
			<div className="profile">
				<div className="row">
					<div className="col profile-img">
						<CompanyThumbnail src={this.state.meta ? this.state.meta.i : null} alt={this.state.meta ? this.state.meta.n : null} maxSize={110} alignTop={true} />
					</div>
					<div className="col profile-content">
						<div className="row profile-title">
							<h2 className="col">{this.state.meta ? this.state.meta.n : null}</h2>
							{tags}
						</div>
						<div className="profile-desc">{this.state.profile ? this.state.profile.description : ''}</div>
						<CompanyProfileSummary profile={this.state.profile} />
						{ this.state.profile !== null ?
						<div className="row">
							<div className="col" style={{width: '550px'}}>
							{this.state.profile.funding_rounds.length > 0 ?
								<div className="profile-section" style={{width: '100%'}}>
									<div className="row section-title">
										<h3 className="col">{'Funding'}</h3>
										{ this.state.profile.total_funding &&  this.state.profile.age ?
										<div className='col-right row'>
											<div className='col rate'>{numeral(Math.round(this.state.profile.total_funding/(this.state.profile.age - 6))).format('($ 0.00a)')}<span className="light">{'/mo'}</span></div>
										</div>
										: null }
									</div>
									<div className="section-subtitle">{'Sum of money raised per year'}</div>
									<div ref="fundingGraph"></div>	
								</div>
								: null
							}
							</div>
							<div className="col-right" style={{width: '270px'}}>
								<CompanyCompetitors permalink={this.props.permalink} />
							</div>
						</div>
						: null
						}				
					</div>
				</div>
			</div>
		);
	}
});

/*var TickerView = React.createClass({
	getDefaultProps: function() {
		return {
			companies: [],
			title: ''
		}
	},

	render: function(){
		var tiles = [];
		this.props.companies.forEach(function(company, i) {
			if(i % 5 === 0 && this.props.title.length > 0) {
				tiles.push(<div className="tile tile-title col">{this.props.title}</div>);
			}
			tiles.push(
				<a className="tile row col" href={'#' + company.p}>
					<div className="tile-img col"><CompanyThumbnail src={company.i} maxSize={50} /></div>
					<div className="tile-label col">{company.n}</div>
				</a>
			);
		}.bind(this));
		return (
			<div className="ticker" style={this.props.style}>
				<div className="ticker-tiles row">
					{tiles}
				</div>
			</div>
		);
	}
});*/

var TrendView = React.createClass({
	getInitialState: function() {
		return {
			stats: null
		}
	},

	getDefaultProps: function(){
		return {
			statsUrl: '/stats' 
		}
	},

	loadStatsFromServer: function(){
		var queryUrl =  this.props.statsUrl;
	    $.ajax({
	      	url: queryUrl,
	      	dataType: 'json',
	      	success: function(data) {
	        	this.setState({stats: data});
	      	}.bind(this),
	      	error: function(xhr, status, err) {
	        	console.error(queryUrl, status, err.toString());
	      	}.bind(this)
	    });
	},

	componentWillMount: function(){
		this.loadStatsFromServer();
	},

	render: function(){
		return (
			<div className="trends">
				<div className="trends-banner">
					<h2>Investup simplifies the process of gaining insight into the growth potential of a company by analyzing patterns and creating a model that predicts success in terms of investment opportunities.</h2>
					<div className="trends-stats">
						{ this.state.stats ?
							<h3>Indexed <span className="emph">{numberWithCommas(this.state.stats.indexed_count)}</span> company profiles across <span className="emph">{this.state.stats.cat_count}</span> categories.</h3>
							: null
						}
					</div>
				</div>

			</div>
		);
	}
});

var AppPages = {
	HOME: 'home',
	SEARCH: 'search',
	PROFILE: 'profile'
};

var App = React.createClass({
	getInitialState: function(){
		return {
			currPage: AppPages.HOME,
			query: '',
			permalink:''
		};
	},

	handleOnQuery: function(q) {
		if(q.length >= 3) {
			this.router.setRoute('/search/' + encodeURIComponent(q));
		}
		else if(this.state.currPage !== AppPages.PROFILE){
			this.router.setRoute('/');
		}
	},

	componentDidMount: function () {
		var setState = this.setState.bind(this);
		var self = this;
		this.router = Router({
			'/': function(){
				setState({currPage: AppPages.HOME})
			},
			'/search/:query': function(query) {
				setState({currPage: AppPages.SEARCH, query: decodeURIComponent(query)});
			},
			'/:permalink': function(permalink) {
				setState({currPage: AppPages.PROFILE, permalink: permalink, query: ''});
			}
		});
		this.router.init();
	},

	render: function() {
		var content;
		if(this.state.currPage == AppPages.HOME) {
			content =
	            <TrendView/>;
		}
		else if(this.state.currPage == AppPages.SEARCH) {
			content =
	            <SearchResultList url="/companies?q=" query={this.state.query} />;
		}
		else if(this.state.currPage == AppPages.PROFILE) {
	        content =
	        	<CompanyProfile permalink={this.state.permalink} />;
		}

		return (
        	<div>
	            <div className="header row">
	            	<div className="wrapper">
		            	<a href="/"><h1 className="logo col">Investup</h1></a>
		                <SearchBar
		                	className="col"
		                	query={this.state.query}
		                	permalink={this.state.permalink}
		                	onQuery={this.handleOnQuery}
		                />
		            </div>
	            </div>
	            <div className="wrapper">
	            	<div className="content-wrapper">
	            		{content}
	            	</div>
	            </div>
	        </div>
		);
	}	
});

React.render(<App />, document.body);