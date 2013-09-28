class CreateEvents < ActiveRecord::Migration
  def change
    create_table :events do |t|
      t.string :name
      t.string :title
      t.date :start_date
      t.date :end_date
      t.string :location_name
      t.text :location_info
      t.text :description
      t.string :url
      t.references :series

      t.timestamps
    end
  end
end
