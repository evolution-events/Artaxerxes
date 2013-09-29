class Series < ActiveRecord::Base
  has_many :events

  def to_s
    name
  end
end
