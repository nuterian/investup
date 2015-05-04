function numberWithCommas(x) {
    return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

var CompanyThumbnail = React.createClass({
	getInitialState: function() {
		return {
			status: 'loading'
		};
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
		if(imgNode.width > imgNode.height) {
			imgNode.style.width = this.props.maxSize + 'px';
			imgNode.style.height = 'auto';
			imgNode.style.marginTop = (this.props.maxSize / 2 - (this.props.maxSize * imgNode.height / imgNode.width) / 2) + 'px';
		}
		else {
			imgNode.style.height = this.props.maxSize + 'px';
			imgNode.style.width = 'auto';
			imgNode.style.marginLeft = (this.props.maxSize / 2 - (this.props.maxSize * imgNode.width / imgNode.height) / 2) + 'px';
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
	    var className = 'thumb-' + this.state.status;
	    return (
	    	<div className={className}>
		    	<div className="spinner"></div>
		      	<img src={this.props.src} alt={this.props.alt} onLoad={this.handleLoad} onError={this.handleError} ref="img"/>
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
            		<CompanyThumbnail src={this.props.company.i} maxSize={maxThumbSize} />
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

var SearchResultList = React.createClass({
	getInitialState: function() {
		return {
			companies: [],
			currentPage: 1,
			status: 'noquery'
		}
	},

	getDefaultProps: function() {
		return {
			pageSize: 10
		}
	},

	loadCompaniesFromServer: function(q) {
		this.setState({status: 'loading'});
		var queryUrl =  this.props.url + q;
	    $.ajax({
	      	url: queryUrl,
	      	dataType: 'json',
	      	success: function(data) {
	        	this.setState({companies: data, currentPage: 1, status: 'loaded'});
	      	}.bind(this),
	      	error: function(xhr, status, err) {
	        	console.error(queryUrl, status, err.toString());
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
	   	var start = this.props.pageSize * (this.state.currentPage - 1);
	    var end = start + this.props.pageSize;

	    return {
	      	currentPage: this.state.currentPage, 
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
        	<div className="list-wrapper">
        		<div className="result-status">{resultStatus}</div>
	        	<ul className="company-list">
	        		{rows}
	        	</ul>
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
		if(nextProps.profile !== null && this.props.profile !== nextProps.profile) {
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

		return (
			<div className={"profile-summary " + this.state.status}>
				{ this.props.profile ?
					<div className="profile-summary-content">
						<div className="profile-panel row">
							<div className="col">
								<div className="profile-label">{"Success chance"}</div>
								<div>{this.props.profile.success || <span className="light">{"n/a"}</span>}</div>
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

var CompanyProfile = React.createClass({
	getInitialState: function(){
		return {
			profile: null,
			status: "loading"			
		}
	},

	getDefaultProps: function() {
		return {
			url: "/profile?p="
		}
	},

	loadCompaniesFromServer: function(p) {
		console.log('loading');
		this.setState({status: "loading"});

		var queryUrl =  this.props.url + p;
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

	componentWillMount: function() {
		this.loadCompaniesFromServer(this.props.permalink);
	},

	componentWillReceiveProps: function(nextprops) {
		if(this.props.permalink !== nextprops.permalink) {
			this.loadProfileFromServer(permalink);
		}
	},

	render: function(){

		return (
			<div className="profile">
				<div className="row">
					<div className="col profile-img">
						<CompanyThumbnail src="" maxSize={100} />
					</div>
					<div className="col profile-content">
						<h2>{this.state.profile ? this.state.profile.name : ''}</h2>
						<div className="profile-desc">{this.state.profile ? this.state.profile.description : ''}</div>
						<CompanyProfileSummary profile={this.state.profile} />
					</div>
				</div>
			</div>
		);
	}
});

var TrendView = React.createClass({
	render: function(){
		return (
				<div>{'Trends will be displayed here.'}</div>
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
			this.router.setRoute('/search/' + q);
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
				setState({currPage: AppPages.SEARCH, query: query});
			},
			'/:permalink': function(permalink) {
				setState({currPage: AppPages.PROFILE, permalink: permalink, query: ''});
			}
		});
		this.router.init();
	},

	render: function() {
		var content;
		console.log('rendering', this.state.currPage);
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