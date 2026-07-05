import Navbar from "../components/Navbar";

function Insights({ events, sources }) {
  // Process events for business insights
  const processEventsForInsights = (events) => {
    if (!events || events.length === 0) {
      return {
        totalChanges: 0,
        categories: {},
        severityDistribution: {},
        timelineData: [],
        recentChanges: [],
        insights: [],
        trends: {
          totalChanges: 0,
          critical: 0,
          high: 0,
          medium: 0,
          low: 0
        }
      };
    }

    // Helper function to filter events by date range
    const filterEventsByDateRange = (startDate, endDate) => {
      return events.filter(event => {
        const eventDate = event.created_at ? new Date(event.created_at) : new Date();
        return eventDate >= startDate && eventDate < endDate;
      });
    };

    // Calculate date ranges for trend analysis
    const now = new Date();
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    const fourteenDaysAgo = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);

    // Current period: last 7 days
    const currentEvents = filterEventsByDateRange(sevenDaysAgo, now);
    // Previous period: 7-14 days ago
    const previousEvents = filterEventsByDateRange(fourteenDaysAgo, sevenDaysAgo);

    // Calculate metrics for current period
    const calculateMetrics = (eventList) => {
      const categories = {};
      const severityDistribution = { critical: 0, high: 0, medium: 0, low: 0 };
      let totalChanges = 0;

      eventList.forEach(event => {
        // Category count
        const category = event.change_type || 'other';
        categories[category] = (categories[category] || 0) + 1;

        // Severity count
        const severity = event.severity || 'low';
        if (severityDistribution[severity] !== undefined) {
          severityDistribution[severity]++;
        }

        totalChanges++;
      });

      return { categories, severityDistribution, totalChanges };
    };

    const currentMetrics = calculateMetrics(currentEvents);
    const previousMetrics = calculateMetrics(previousEvents);

    // Calculate trends (difference from previous period)
    const trends = {
      totalChanges: currentMetrics.totalChanges - previousMetrics.totalChanges,
      critical: currentMetrics.severityDistribution.critical - previousMetrics.severityDistribution.critical,
      high: currentMetrics.severityDistribution.high - previousMetrics.severityDistribution.high,
      medium: currentMetrics.severityDistribution.medium - previousMetrics.severityDistribution.medium,
      low: currentMetrics.severityDistribution.low - previousMetrics.severityDistribution.low
    };

    // Count by category (current period)
    const categories = currentMetrics.categories;
    const severityDistribution = currentMetrics.severityDistribution;
    const timelineData = [];
    const recentChanges = events.slice(0, 5); // Last 5 changes overall

    events.forEach(event => {
      // Timeline data (simplified - group by date)
      const date = event.created_at ? new Date(event.created_at).toISOString().split('T')[0] : new Date().toISOString().split('T')[0];
      const existingDay = timelineData.find(day => day.date === date);
      if (existingDay) {
        existingDay.count++;
      } else {
        timelineData.push({ date, count: 1 });
      }
    });

    // Generate business insights
    const insights = [];

    if (events.length > 0) {
      const total = events.length;
      const criticalCount = severityDistribution.critical;
      const highCount = severityDistribution.high;

      if (criticalCount > 0) {
        insights.push({
          type: 'warning',
          icon: '⚠️',
          title: 'Immediate Attention Required',
          description: `${criticalCount} critical changes detected that may significantly impact your competitive position. Review these immediately.`
        });
      }

      if (highCount > criticalCount) {
        insights.push({
          type: 'info',
          icon: '📈',
          title: 'Notable Market Activity',
          description: `${highCount} high-priority changes suggest active competitor movements in pricing, features, or messaging.`
        });
      }

      // Find most active category
      let topCategory = null;
      let maxCount = 0;
      Object.entries(categories).forEach(([cat, count]) => {
        if (count > maxCount) {
          maxCount = count;
          topCategory = cat;
        }
      });

      if (topCategory && maxCount > 0) {
        const categoryNames = {
          price: 'Pricing Strategies',
          keyword: 'SEO & Content Tactics',
          messaging: 'Brand Messaging & Positioning',
          anomaly: 'Unusual Market Activities'
        };
        const displayName = categoryNames[topCategory] || topCategory;
        insights.push({
          type: 'info',
          icon: '🎯',
          title: 'Primary Competitive Focus',
          description: `Competitors are most actively changing their ${displayName.toLowerCase()} (${maxCount} changes detected).`
        });
      }

      if (total > 10) {
        insights.push({
          type: 'positive',
          icon: '✅',
          title: 'Active Market Monitoring',
          description: `Your competitive intelligence system is tracking ${total} changes, providing comprehensive market visibility.`
        });
      } else if (total > 0) {
        insights.push({
          type: 'info',
          icon: '🔍',
          title: 'Gathering Competitive Intelligence',
          description: `Monitoring detected ${total} competitive changes. Continue to gather data for stronger insights.`
        });
      }
    } else {
      insights.push({
        type: 'info',
        icon: '📊',
        title: 'No Competitive Activity Detected',
        description: `No changes have been detected yet. Adding competitors and initiating crawls will begin generating competitive intelligence.`
      });
    }

    return {
      totalChanges: events.length,
      categories,
      severityDistribution,
      timelineData: timelineData.slice(0, 7), // Last 7 days
      recentChanges,
      insights,
      trends: {
        totalChanges: trends.totalChanges,
        critical: trends.critical,
        high: trends.high,
        medium: trends.medium,
        low: trends.low
      }
    };
  };

  const { totalChanges, categories, severityDistribution, timelineData, recentChanges, insights, trends } = processEventsForInsights(events);

  return (
    <div>
      <Navbar />
      <h2 className="text-2xl font-bold mb-6 text-gradient">Competitive Intelligence Insights</h2>
      <p className="text-muted mb-6">
        Strategic overview of competitor activities and market movements
      </p>

      {/* Executive Summary */}
      <div className="glass-card p-6 mb-6">
        <h3 className="font-semibold mb-4">Executive Summary</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="glass p-4 text-center border-l-4 border-blue-500">
            <div className="text-3xl font-bold text-blue-600">{totalChanges}</div>
            {trends.totalChanges !== 0 && (
              <div className={`text-sm ${trends.totalChanges > 0 ? 'text-green-600' : 'text-red-600'} mt-1`}>
                {trends.totalChanges > 0 ? `+${trends.totalChanges}` : trends.totalChanges} vs last week
              </div>
            )}
            <div className="text-sm text-muted">Total Changes Detected</div>
          </div>
          <div className="glass p-4 text-center border-l-4 border-red-500">
            <div className="text-3xl font-bold text-red-600">{severityDistribution.critical}</div>
            {trends.critical !== 0 && (
              <div className={`text-sm ${trends.critical > 0 ? 'text-green-600' : 'text-red-600'} mt-1`}>
                {trends.critical > 0 ? `+${trends.critical}` : trends.critical} vs last week
              </div>
            )}
            <div className="text-sm text-muted">Critical Alerts</div>
          </div>
          <div className="glass p-4 text-center border-l-4 border-orange-500">
            <div className="text-3xl font-bold text-orange-600">{severityDistribution.high}</div>
            {trends.high !== 0 && (
              <div className={`text-sm ${trends.high > 0 ? 'text-green-600' : 'text-red-600'} mt-1`}>
                {trends.high > 0 ? `+${trends.high}` : trends.high} vs last week
              </div>
            )}
            <div className="text-sm text-muted">High Priority Changes</div>
          </div>
          <div className="glass p-4 text-center border-l-4 border-green-500">
            <div className="text-3xl font-bold text-green-600">{severityDistribution.medium + severityDistribution.low}</div>
            {((trends.medium + trends.low) !== 0) && (
              <div className={`text-sm ${(trends.medium + trends.low) > 0 ? 'text-green-600' : 'text-red-600'} mt-1`}>
                {(trends.medium + trends.low) > 0 ? `+${trends.medium + trends.low}` : (trends.medium + trends.low)} vs last week
              </div>
            )}
            <div className="text-sm text-muted">Routine Updates</div>
          </div>
        </div>
      </div>

      {/* Business Insights */}
      <div className="glass-card p-6 mb-6">
        <h3 className="font-semibold mb-4">Key Business Insights</h3>
        {insights.length === 0 ? (
          <p className="text-muted">No significant insights to display at this time.</p>
        ) : (
          <div className="space-y-3">
            {insights.map((insight, index) => {
              // Define color mapping based on insight type
              const colorMap = {
                warning: '#ef4444', // red-500 for critical/warning
                info: {
                  default: '#3b82f6', // blue-500 for general info
                  marketActivity: '#f97316', // orange-500 for market activity
                  competitiveFocus: '#6366f1', // indigo-500 for competitive focus
                  gatheringIntel: '#3b82f6' // blue-500 for gathering intel
                },
                positive: '#10b981', // green-500 for positive
              };

              let bgColor = '#6b7280'; // default gray-500
              if (insight.type === 'warning') {
                bgColor = colorMap.warning;
              } else if (insight.type === 'positive') {
                bgColor = colorMap.positive;
              } else if (insight.type === 'info') {
                // Determine specific info type based on title
                if (insight.title === 'Notable Market Activity') {
                  bgColor = colorMap.info.marketActivity;
                } else if (insight.title === 'Primary Competitive Focus') {
                  bgColor = colorMap.info.competitiveFocus;
                } else if (insight.title === 'Gathering Competitive Intelligence') {
                  bgColor = colorMap.info.gatheringIntel;
                } else {
                  bgColor = colorMap.info.default;
                }
              }

              return (
                <div key={index} className="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg">
                  <div className="flex-shrink-0 mt-1 flex h-3 w-3 items-center justify-center">
                    <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: bgColor }}></div>
                  </div>
                  <div>
                    <h4 className="font-semibold">{insight.title}</h4>
                    <p className="text-sm text-muted">{insight.description}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Category Breakdown */}
      <div className="glass-card p-6 mb-6">
        <h3 className="font-semibold mb-4">Change Categories</h3>
        {Object.keys(categories).length === 0 ? (
          <p className="text-muted">No category data available.</p>
        ) : (
          <div className="w-full space-y-3">
            {(() => {
              const categoryNames = {
                price: 'Pricing Strategies',
                keyword: 'SEO & Content Tactics',
                messaging: 'Brand Messaging & Positioning',
                anomaly: 'Unusual Market Activities'
              };
              const colorMap = {
                price: '#3b82f6',
                keyword: '#10b981',
                messaging: '#8b5cf6',
                anomaly: '#f59e0b'
              };
              const maxCount = Math.max(...Object.values(categories)) || 1;

              return Object.entries(categories)
                .sort((a, b) => b[1] - a[1])
                .map(([category, count]) => {
                  const displayName = categoryNames[category] || category;
                  const barColor = colorMap[category] || '#6b7280';
                  const pct = Math.max((count / maxCount) * 100, 4);

                  return (
                    <div key={category} className="flex items-center gap-3">
                      <div className="w-40 md:w-52 shrink-0 text-sm text-right text-muted">
                        {displayName}
                      </div>
                      <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                        <div
                          className="h-4 rounded-full flex items-center justify-end pr-2"
                          style={{ width: `${pct}%`, backgroundColor: barColor }}
                        >
                          {pct > 15 && (
                            <span className="text-[11px] font-semibold text-white">{count}</span>
                          )}
                        </div>
                      </div>
                      {pct <= 15 && (
                        <div className="w-6 text-xs font-semibold text-left">{count}</div>
                      )}
                    </div>
                  );
                });
            })()}

            <p className="text-sm text-muted mt-2">
              Bar length represents the number of changes detected in each category.
            </p>
          </div>
        )}
      </div>

      {/* Recent Activity Timeline */}
      <div className="glass-card p-6 mb-6">
        <h3 className="font-semibold mb-4">Recent Activity Trend</h3>
        {timelineData.length === 0 ? (
          <p className="text-muted">No timeline data available.</p>
        ) : (
          <div className="space-y-3">
            {timelineData.map((day, index) => (
              <div key={index} className="flex items-center space-x-3 p-2 bg-gray-50 rounded-lg">
                <div className="w-20 text-right text-xs font-medium">{day.date}</div>
                <div className="flex-1 bg-gray-200 rounded-full h-2.5">
                  <div className="bg-indigo-600 h-2.5 rounded-full" style={{ width: Math.min((day.count / (Math.max(...timelineData.map(d => d.count)) || 1)) * 100, 100) }}></div>
                </div>
                <div className="w-12 text-center text-xs font-semibold">{day.count}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Actionable Recommendations */}
      <div className="glass-card p-6">
        <h3 className="font-semibold mb-4">Recommended Actions</h3>
        <div className="space-y-4">
          <div className="flex items-start space-x-3 p-3 bg-blue-50 rounded-lg border-l-4 border-blue-500">
            <div className="flex-shrink-0 mt-1">🚀</div>
            <div>
              <h4 className="font-semibold">Monitor Critical Changes</h4>
              <p className="text-sm text-muted">Set up alerts for critical competitor changes that require immediate response.</p>
            </div>
          </div>
          <div className="flex items-start space-x-3 p-3 bg-green-50 rounded-lg border-l-4 border-green-500">
            <div className="flex-shrink-0 mt-1">📊</div>
            <div>
              <h4 className="font-semibold">Analyze Patterns</h4>
              <p className="text-sm text-muted">Look for recurring patterns in competitor behavior to anticipate future moves.</p>
            </div>
          </div>
          <div className="flex items-start space-x-3 p-3 bg-orange-50 rounded-lg border-l-4 border-orange-500">
            <div className="flex-shrink-0 mt-1">🎯</div>
            <div>
              <h4 className="font-semibold">Strategic Response Planning</h4>
              <p className="text-sm text-muted">Develop proactive strategies based on observed competitor weaknesses and opportunities.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Insights;